import os
import json
import urllib.request
from http.server import BaseHTTPRequestHandler
from datetime import datetime

def kirim_ke_telegram(pesan):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
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
            pass
    except Exception as e:
        print(f"Gagal kirim Telegram: {e}")

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
        # 1. Ambil semua data header untuk pengecekan
        content_length = int(self.headers.get('Content-Length') or 0)
        content_type = self.headers.get('Content-Type', 'unknown')
        
        # 2. Baca data mentah dari frontend
        if content_length > 0:
            try:
                post_data = self.rfile.read(content_length).decode('utf-8')
            except Exception as e:
                post_data = f"(Gagal membaca body: {e})"
        else:
            post_data = "(BODY KOSONG / NO DATA)"

        # 3. KITA PAKSA KIRIM APAPUN YANG DIDAPAT KE TELEGRAM
        pesan_debug = (
            f"🔔 *WEB EVENT LOG* 🔔\n\n"
            f"📊 *Status:* Scan Selesai Dipicu\n"
            f"📦 *Content-Type:* {content_type}\n"
            f"📏 *Content-Length:* {content_length}\n"
            f"📝 *Data Mentah Kiriman Web:* \n`{post_data}`\n\n"
            f"⏰ *Waktu:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} WIB"
        )
        
        kirim_ke_telegram(pesan_debug)

        # 4. Beri respons balik ke Web agar tidak hang
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "success", "received": True}).encode('utf-8'))
