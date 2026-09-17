"""DPAPI-encrypted private records. SQL indices contain opaque ids, never mail text."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import os
import sqlite3
import stat
import time
import uuid
from runtime import REPO
from secure_store import ConnectorError, WindowsProtector, records_root, guard_repository_location

KINDS={'case','mail','body','blob','artifact','sync','issue','event','campaign','workspace','template','destination'}

class Database:
    def __init__(self,root=None,protector=None):
        self.root=root if root is not None else records_root()
        self.protector=protector or WindowsProtector()
    def guard(self):
        # Modified 2026-09-10: reject every Git working tree after extraction.
        guard_repository_location(self.root,REPO)
        for p in (self.root,*self.root.parents):
            if p.exists() or p.is_symlink():
                info=p.lstat()
                if p.is_symlink() or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0):
                    raise ConnectorError('Private storage cannot use redirected paths.')
        if self.root.exists():
            for p in self.root.iterdir():
                info=p.lstat()
                if p.is_symlink() or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0) or (p.is_file() and info.st_nlink>1):
                    raise ConnectorError('Private files cannot use links or junctions.')
    @contextmanager
    def connect(self,readonly=False):
        self.guard(); path=self.root/'records.sqlite3'
        if readonly and not path.exists():
            yield None; return
        if not readonly:self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        con=sqlite3.connect(path.resolve().as_uri()+('?mode=ro' if readonly else '?mode=rwc'),uri=True,timeout=10)
        con.row_factory=sqlite3.Row
        try:
            if not readonly:
                con.execute('PRAGMA synchronous=FULL')
                con.execute('CREATE TABLE IF NOT EXISTS records(kind TEXT NOT NULL,id TEXT NOT NULL,rev INTEGER NOT NULL,payload BLOB NOT NULL,PRIMARY KEY(kind,id))')
                con.execute('CREATE TABLE IF NOT EXISTS lease(id INTEGER PRIMARY KEY CHECK(id=1),owner TEXT NOT NULL,expires REAL NOT NULL)')
            with con:yield con
        finally:con.close()
    def decode(self,row):
        value=self.protector.unprotect(row['payload'])
        if (value.get('kind'),value.get('id'),value.get('rev'))!=(row['kind'],row['id'],row['rev']):
            raise ConnectorError('Encrypted record identity does not match its index. Stop and review local storage.')
        data=value.get('value')
        if not isinstance(data,dict):raise ConnectorError('Encrypted record value is invalid.')
        if row['kind'] in {'case','mail','body','artifact','issue','event','campaign','workspace','template','destination'} and data.get('id')!=row['id']:
            raise ConnectorError('Private record inner identity does not match its envelope.')
        if row['kind']=='mail':
            expected=f"{data.get('folder')}:{data.get('uid_validity')}:{data.get('uid')}"
            if expected!=row['id']:raise ConnectorError('Mail identity does not match its UID-bound envelope.')
        if row['kind']=='sync' and data.get('folder')!=row['id']:raise ConnectorError('Mail cursor folder identity changed.')
        return value['value']
    def get(self,kind,key,default=None):
        with self.connect(True) as con:
            row=con.execute('SELECT * FROM records WHERE kind=? AND id=?',(kind,key)).fetchone() if con else None
            return self.decode(row) if row else default
    def all(self,kind):
        if kind=='blob':raise ConnectorError('Bulk attachment reads are not available.')
        with self.connect(True) as con:
            return [self.decode(r) for r in con.execute('SELECT * FROM records WHERE kind=? ORDER BY id',(kind,))] if con else []
    def put(self,kind,key,value):
        if kind not in KINDS or not isinstance(key,str) or not 1<=len(key)<=250:raise ConnectorError('Invalid private record identity.')
        if kind in {'case','mail','body','artifact','issue','event','campaign','workspace','template','destination'} and value.get('id')!=key:raise ConnectorError('Private record identity mismatch.')
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute('SELECT * FROM records WHERE kind=? AND id=?',(kind,key)).fetchone()
            if row:self.decode(row)
            if not row and con.execute('SELECT COUNT(*) FROM records').fetchone()[0]>=20000:
                raise ConnectorError('Private record capacity reached. Archive records through a reviewed maintenance step.')
            if (self.root/'records.sqlite3').stat().st_size>750*1024*1024:
                raise ConnectorError('The local 750 MiB capacity limit was reached. No records were discarded.')
            rev=(row['rev'] if row else 0)+1
            payload=self.protector.protect({'kind':kind,'id':key,'rev':rev,'value':value})
            con.execute('INSERT INTO records VALUES(?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET rev=excluded.rev,payload=excluded.payload',(kind,key,rev,payload))
    @contextmanager
    def operation(self):
        # Serialize mutations across the web server and independently launched MCP workers.
        owner=str(uuid.uuid4())
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute('SELECT * FROM lease WHERE id=1').fetchone()
            if row and row['expires']>time.time():raise ConnectorError('Another records operation is running. Wait for it to finish.')
            con.execute('INSERT OR REPLACE INTO lease VALUES(1,?,?)',(owner,time.time()+300))
        try:yield
        finally:
            with self.connect() as con:con.execute('DELETE FROM lease WHERE id=1 AND owner=?',(owner,))
    def event(self,case_id,action,details):
        key=str(uuid.uuid4())
        self.put('event',key,{'id':key,'case_id':case_id,'action':action,'at':time.time(),'details':details})
