import json
import sys
from service import safe_dispatch

def main():
    raw=sys.stdin.buffer.read(300001)
    if len(raw)>300000:result={'ok':False,'error':'Request exceeds the local size limit.'}
    else:
        try:
            request=json.loads(raw)
            if set(request)!={'tool','arguments'}:raise ValueError()
            result=safe_dispatch(request['tool'],request['arguments'])
        except Exception:result={'ok':False,'error':'Invalid local request.'}
    sys.stdout.buffer.write(json.dumps(result,ensure_ascii=False).encode('utf-8'))

if __name__=='__main__':main()
