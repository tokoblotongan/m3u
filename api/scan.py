"""
IPTV Scan API — cek status stream (alive/dead) server-side.
Menghindari browser CORS restriction dan IP block.
"""
import json
import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAG_UA = (
    "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 "
    "(KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3"
)

def check_stream(url, timeout=8):
    if not url or "://" not in str(url):
        return False, "No URL"
    try:
        h = {"User-Agent": MAG_UA, "Connection": "close", "Accept": "*/*"}
        with requests.get(url, timeout=timeout, stream=True, headers=h, verify=False) as r:
            if r.status_code not in (200, 206):
                return False, f"HTTP {r.status_code}"
            ctype = r.headers.get("Content-Type", "").lower()
            if any(x in ctype for x in ["text/html", "application/json", "text/plain"]):
                return False, "HTML/JSON response"
            chunk = r.raw.read(8192)
            alive = len(chunk) > 512
            return alive, "OK" if alive else "Empty chunk"
    except requests.exceptions.Timeout:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)[:60]


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _cors(self):
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in self._cors().items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        b = json.dumps({"status": "ok", "service": "IPTV Scan API v9"}).encode()
        self.send_response(200)
        for k, v in self._cors().items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) if length else b"{}")
        except Exception as e:
            self._err(400, f"Bad JSON: {e}")
            return

        urls = body.get("urls", [])
        workers = min(int(body.get("workers", 10)), 20)
        timeout = min(int(body.get("timeout", 8)), 15)

        if not urls:
            self._err(400, "urls wajib diisi")
            return
        if len(urls) > 200:
            urls = urls[:200]  # max 200 per request

        results = {}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            future_map = {ex.submit(check_stream, u, timeout): u for u in urls}
            for future in as_completed(future_map):
                url = future_map[future]
                try:
                    alive, reason = future.result()
                    results[url] = {"alive": alive, "reason": reason}
                except Exception as e:
                    results[url] = {"alive": False, "reason": str(e)[:60]}

        alive_count = sum(1 for v in results.values() if v["alive"])
        b = json.dumps({
            "ok": True,
            "total": len(results),
            "alive": alive_count,
            "dead": len(results) - alive_count,
            "results": results,
        }).encode()
        self.send_response(200)
        for k, v in self._cors().items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _err(self, code, msg):
        b = json.dumps({"ok": False, "error": msg}).encode()
        self.send_response(code)
        for k, v in self._cors().items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
