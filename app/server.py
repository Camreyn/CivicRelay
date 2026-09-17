"""Loopback-only private records desk. No cloud hosting or remote assets."""
from __future__ import annotations
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json
import hashlib
import secrets
import urllib.parse
from runtime import PYTHON, run
from service import ARGUMENTS

ROOT = Path(__file__).resolve().parent
PORT = 8766
ORIGIN = f"http://127.0.0.1:{PORT}"
COOKIE = secrets.token_urlsafe(32)
# Added for standalone extraction: distinguish this checkout from legacy servers.
INSTALLATION_ID = hashlib.sha256(str(ROOT.parent).lower().encode('utf-8')).hexdigest()
def invoke(name,args):
    result=run([PYTHON,'-E','-s','-S',str(ROOT/'worker.py')],
               payload=json.dumps({'tool':name,'arguments':args}).encode(),timeout=220)
    if result.returncode or len(result.stdout)>8_000_000:
        return {'ok':False,'error':'The worker did not return a bounded result. Inspect saved receipts before retrying any external write.'}
    try:return json.loads(result.stdout)
    except ValueError:return {'ok':False,'error':'Local worker response was unavailable. No private diagnostics were exposed.'}

class Handler(BaseHTTPRequestHandler):
    server_version = 'RecordsDesk'
    def log_message(self,*args): pass  # Do not put mailbox data or request bodies in logs.
    def reply_headers(self,code,ctype,length,cookie=False):
        self.send_response(code)
        for key,value in {
            'Content-Type':ctype,'Content-Length':str(length),'Cache-Control':'no-store',
            'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
            'Cross-Origin-Resource-Policy':'same-origin',
            'Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        }.items(): self.send_header(key,value)
        if cookie: self.send_header('Set-Cookie',f'records_session={COOKIE}; HttpOnly; SameSite=Strict; Path=/')
        self.end_headers()
    def json(self,data,code=200):
        raw=json.dumps(data,ensure_ascii=False).encode()
        self.reply_headers(code,'application/json; charset=utf-8',len(raw)); self.wfile.write(raw)
    def allowed(self,session=False):
        if self.headers.get('Host') != f'127.0.0.1:{PORT}': return False
        if self.headers.get('Origin') not in (None,ORIGIN): return False
        if self.headers.get('Sec-Fetch-Site') not in (None,'none','same-origin'): return False
        return not session or f'records_session={COOKIE}' in self.headers.get('Cookie','').split('; ')
    def do_GET(self):
        if not self.allowed(): return self.json({'ok':False,'error':'Local origin required.'},403)
        route=urllib.parse.urlsplit(self.path).path
        if route=='/health': return self.json({'ok':True,'app':'CivicResultMaps Records Desk','local_only':True,'tooling_version':'0.6.1',
            'distribution':'civic-records-desk','package_version':'0.6.1','installation_id':INSTALLATION_ID})
        if route.startswith('/api/'):
            if not self.allowed(True): return self.json({'ok':False,'error':'Open the local dashboard first.'},403)
            if route=='/api/bootstrap':
                try:
                    result=invoke('desk_list_cases',{})
                    return self.json({'ok':True,**result['result']} if result['ok'] else result)
                except Exception:return self.json({'ok':False,'error':'Could not open private records. Use your normal Windows desktop session.'},500)
            return self.json({'ok':False,'error':'Unknown route.'},404)
        files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/workspace.js':('workspace.js','text/javascript; charset=utf-8'),
               '/tool-contracts.mjs':('tool-contracts.mjs','text/javascript; charset=utf-8'),'/page-tools.mjs':('page-tools.mjs','text/javascript; charset=utf-8'),
               '/general-contracts.mjs':('general-contracts.mjs','text/javascript; charset=utf-8'),
               '/send-controls.mjs':('send-controls.mjs','text/javascript; charset=utf-8'),
               '/equipment-campaign.js':('equipment-campaign.js','text/javascript; charset=utf-8'),
               '/general-workspace.js':('general-workspace.js','text/javascript; charset=utf-8'),
               '/general.css':('general.css','text/css; charset=utf-8'),
               '/style.css':('style.css','text/css; charset=utf-8'),'/status.css':('status.css','text/css; charset=utf-8'),'/map.json':('map.json','application/json')}
        if route not in files:return self.json({'ok':False,'error':'Not found.'},404)
        name,ctype=files[route]; raw=(ROOT/'static'/name).read_bytes()
        self.reply_headers(200,ctype,len(raw),cookie=route=='/'); self.wfile.write(raw)
    def do_POST(self):
        if not self.allowed(True) or self.headers.get('Origin')!=ORIGIN or self.headers.get('X-Records-Desk')!='1':
            return self.json({'ok':False,'error':'A same-origin dashboard request is required.'},403)
        if self.path!='/api/operation' or self.headers.get_content_type()!='application/json':
            return self.json({'ok':False,'error':'Unknown operation endpoint.'},400)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 1<=size<=300000:raise ValueError()
            self.connection.settimeout(15)
            payload=json.loads(self.rfile.read(size))
            if set(payload)!={'tool','arguments'} or payload['tool'] not in ARGUMENTS:raise ValueError()
            result=invoke(payload['tool'],payload['arguments'])
            return self.json(result,200 if result.get('ok') else 400)
        except Exception:
            return self.json({'ok':False,'error':'Operation interrupted or invalid. Check saved receipts before retrying any send/publication.'},400)

class Server(ThreadingHTTPServer):
    daemon_threads=True
    def handle_error(self,*args):pass

if __name__=='__main__':
    httpd=Server(('127.0.0.1',PORT),Handler)
    print(f'Records Desk ready at {ORIGIN}',flush=True)
    httpd.serve_forever()
