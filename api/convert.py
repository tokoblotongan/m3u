"""
IPTV Proxy — mengatasi CORS dan IP blocking dari browser.
Semua request ke portal IPTV dilewatkan melalui server ini.
"""
import json
import re
import requests
import urllib3
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, quote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAG_UA = (
    "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 "
    "(KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3"
)

TIMEOUT = 15

def _cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Content-Type": "application/json",
    }

def _err(handler, code, msg):
    body = json.dumps({"ok": False, "error": msg}).encode()
    handler.send_response(code)
    for k, v in _cors_headers().items():
        handler.send_header(k, v)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def _ok(handler, data):
    body = json.dumps(data).encode()
    handler.send_response(200)
    for k, v in _cors_headers().items():
        handler.send_header(k, v)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silence default logging

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in _cors_headers().items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        _err(self, 405, "Use POST")

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) if length else b"{}")
        except Exception as e:
            _err(self, 400, f"Bad JSON: {e}")
            return

        action = body.get("action", "")

        if action == "handshake":
            self._do_handshake(body)
        elif action == "get_channels":
            self._do_get_channels(body)
        elif action == "create_link":
            self._do_create_link(body)
        elif action == "xtream_info":
            self._do_xtream_info(body)
        elif action == "xtream_live":
            self._do_xtream_live(body)
        elif action == "xtream_vod":
            self._do_xtream_vod(body)
        elif action == "check_stream":
            self._do_check_stream(body)
        elif action == "fetch_m3u":
            self._do_fetch_m3u(body)
        else:
            _err(self, 400, f"Unknown action: {action}")

    # ─── MAC / Stalker ───────────────────────────────────────────────
    def _mac_session(self, portal, mac):
        s = requests.Session()
        s.verify = False
        s.headers.update({
            "User-Agent": MAG_UA,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{portal}portal.php",
        })
        s.cookies.update({"mac": mac, "stb_lang": "en", "timezone": "Europe/Amsterdam"})
        return s

    def _do_handshake(self, body):
        portal = body.get("portal", "").rstrip("/") + "/"
        mac = body.get("mac", "").strip().upper()
        if not portal or not mac:
            _err(self, 400, "portal dan mac wajib diisi")
            return
        try:
            s = self._mac_session(portal, mac)
            r = s.get(
                f"{portal}portal.php?type=stb&action=handshake&JsHttpRequest=1-xml",
                timeout=TIMEOUT,
            )
            data = r.json()
            js = data.get("js", {})
            token = js.get("token") if isinstance(js, dict) else None

            # Get profile
            profile = {}
            if token:
                s.headers["Authorization"] = f"Bearer {token}"
            try:
                pr = s.get(
                    f"{portal}portal.php?type=account_info&action=get_main_info&JsHttpRequest=1-xml",
                    timeout=TIMEOUT,
                )
                pjs = pr.json().get("js", {})
                if isinstance(pjs, dict):
                    fname = (pjs.get("fname", "") + " " + pjs.get("lname", "")).strip()
                    profile = {
                        "name": fname or "Unknown",
                        "expiry": pjs.get("phone", "") or pjs.get("end_date", "") or "Unlimited",
                        "mac": mac,
                    }
            except Exception:
                pass

            _ok(self, {"ok": True, "token": token, "profile": profile})
        except Exception as e:
            _err(self, 502, f"Handshake gagal: {e}")

    def _do_get_channels(self, body):
        portal = body.get("portal", "").rstrip("/") + "/"
        mac = body.get("mac", "").strip().upper()
        token = body.get("token", "")
        try:
            s = self._mac_session(portal, mac)
            if token:
                s.headers["Authorization"] = f"Bearer {token}"

            # try get_all_channels first
            r = s.get(
                f"{portal}portal.php?type=itv&action=get_all_channels&JsHttpRequest=1-xml",
                timeout=TIMEOUT,
            )
            js = r.json().get("js", {})
            if isinstance(js, dict) and js.get("data"):
                _ok(self, {"ok": True, "channels": js["data"], "total": len(js["data"])})
                return

            # fallback: paginate
            all_ch, page = [], 1
            while True:
                r = s.get(
                    f"{portal}portal.php?type=itv&action=get_ordered_list"
                    f"&genre=*&p={page}&JsHttpRequest=1-xml",
                    timeout=TIMEOUT,
                )
                js = r.json().get("js", {})
                if not isinstance(js, dict):
                    break
                data = js.get("data", [])
                total = int(js.get("total_items", 0))
                if not data:
                    break
                all_ch.extend(data)
                if total and len(all_ch) >= total:
                    break
                if len(data) < 14:
                    break
                page += 1

            _ok(self, {"ok": True, "channels": all_ch, "total": len(all_ch)})
        except Exception as e:
            _err(self, 502, f"Get channels gagal: {e}")

    def _do_create_link(self, body):
        portal = body.get("portal", "").rstrip("/") + "/"
        mac = body.get("mac", "").strip().upper()
        token = body.get("token", "")
        cmd = body.get("cmd", "")
        try:
            s = self._mac_session(portal, mac)
            if token:
                s.headers["Authorization"] = f"Bearer {token}"
            cmd_encoded = quote(str(cmd), safe=":/?&= #")
            r = s.get(
                f"{portal}portal.php?type=itv&action=create_link"
                f"&cmd={cmd_encoded}&JsHttpRequest=1-xml",
                timeout=10,
            )
            js = r.json().get("js", {})
            if isinstance(js, dict):
                raw = str(js.get("cmd", "") or js.get("url", "")).strip()
                for part in reversed(raw.split()):
                    if "://" in part:
                        _ok(self, {"ok": True, "url": part})
                        return
            _ok(self, {"ok": True, "url": ""})
        except Exception as e:
            _err(self, 502, f"Create link gagal: {e}")

    # ─── Xtream ──────────────────────────────────────────────────────
    def _do_xtream_info(self, body):
        server = body.get("server", "").rstrip("/")
        user = body.get("user", "")
        passwd = body.get("passwd", "")
        try:
            r = requests.get(
                f"{server}/player_api.php?username={user}&password={passwd}",
                timeout=TIMEOUT, verify=False,
                headers={"User-Agent": "VLC/3.0.18"},
            )
            _ok(self, {"ok": True, "data": r.json()})
        except Exception as e:
            _err(self, 502, f"Xtream info gagal: {e}")

    def _do_xtream_live(self, body):
        server = body.get("server", "").rstrip("/")
        user = body.get("user", "")
        passwd = body.get("passwd", "")
        try:
            cats = {}
            try:
                cr = requests.get(
                    f"{server}/player_api.php?username={user}&password={passwd}&action=get_live_categories",
                    timeout=TIMEOUT, verify=False, headers={"User-Agent": "VLC/3.0.18"},
                )
                cats = {str(c["category_id"]): c["category_name"] for c in cr.json()}
            except Exception:
                pass

            r = requests.get(
                f"{server}/player_api.php?username={user}&password={passwd}&action=get_live_streams",
                timeout=30, verify=False, headers={"User-Agent": "VLC/3.0.18"},
            )
            channels = []
            for ch in r.json():
                cid = str(ch.get("category_id", ""))
                channels.append({
                    "name": ch.get("name", "Unknown"),
                    "group": cats.get(cid) or ch.get("category_name", "Live TV"),
                    "logo": ch.get("stream_icon", ""),
                    "epg_id": ch.get("epg_channel_id", ""),
                    "stream_id": ch.get("stream_id"),
                    "num": ch.get("num", ""),
                })
            _ok(self, {"ok": True, "channels": channels})
        except Exception as e:
            _err(self, 502, f"Xtream live gagal: {e}")

    def _do_xtream_vod(self, body):
        server = body.get("server", "").rstrip("/")
        user = body.get("user", "")
        passwd = body.get("passwd", "")
        try:
            cats = {}
            try:
                cr = requests.get(
                    f"{server}/player_api.php?username={user}&password={passwd}&action=get_vod_categories",
                    timeout=TIMEOUT, verify=False, headers={"User-Agent": "VLC/3.0.18"},
                )
                cats = {str(c["category_id"]): c["category_name"] for c in cr.json()}
            except Exception:
                pass

            r = requests.get(
                f"{server}/player_api.php?username={user}&password={passwd}&action=get_vod_streams",
                timeout=30, verify=False, headers={"User-Agent": "VLC/3.0.18"},
            )
            vods = []
            for v in r.json():
                cid = str(v.get("category_id", ""))
                vods.append({
                    "name": v.get("name", "Unknown"),
                    "group": cats.get(cid, "VOD"),
                    "logo": v.get("stream_icon", ""),
                    "stream_id": v.get("stream_id"),
                })
            _ok(self, {"ok": True, "channels": vods})
        except Exception as e:
            _err(self, 502, f"Xtream VOD gagal: {e}")

    # ─── Stream check ────────────────────────────────────────────────
    def _do_check_stream(self, body):
        url = body.get("url", "")
        if not url or "://" not in url:
            _ok(self, {"ok": True, "alive": False, "reason": "No URL"})
            return
        try:
            headers = {"User-Agent": MAG_UA, "Connection": "close", "Accept": "*/*"}
            with requests.get(url, timeout=10, stream=True, headers=headers, verify=False) as r:
                if r.status_code not in (200, 206):
                    _ok(self, {"ok": True, "alive": False, "reason": f"HTTP {r.status_code}"})
                    return
                ctype = r.headers.get("Content-Type", "").lower()
                if any(x in ctype for x in ["text/html", "application/json"]):
                    _ok(self, {"ok": True, "alive": False, "reason": "HTML response"})
                    return
                chunk = r.raw.read(8192)
                alive = len(chunk) > 512
                _ok(self, {"ok": True, "alive": alive, "reason": "OK" if alive else "Empty"})
        except Exception as e:
            _ok(self, {"ok": True, "alive": False, "reason": str(e)[:80]})

    def _do_fetch_m3u(self, body):
        url = body.get("url", "")
        try:
            r = requests.get(url, timeout=20, verify=False,
                             headers={"User-Agent": "VLC/3.0.18 LibVLC/3.0.18"})
            r.raise_for_status()
            content = r.text
            if "#EXTM3U" not in content and "extinf" not in content.lower()[:500]:
                _err(self, 400, "Bukan file M3U/M3U8 yang valid")
                return
            _ok(self, {"ok": True, "content": content[:500000]})  # max 500KB
        except Exception as e:
            _err(self, 502, f"Fetch M3U gagal: {e}")
