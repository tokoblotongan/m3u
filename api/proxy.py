"""
IPTV Proxy v9-fix — server-side proxy anti-CORS, anti-block.
Fix: robust JSON parsing, handle empty/HTML responses, better error messages.
"""
import json
import requests
import urllib3
from http.server import BaseHTTPRequestHandler
from urllib.parse import quote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAG_UA = (
    "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 "
    "(KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3"
)
VLC_UA = "VLC/3.0.18 LibVLC/3.0.18"
TIMEOUT = 20

# ─── helpers ────────────────────────────────────────────────────────────────

def cors():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Content-Type": "application/json",
    }

def send_json(h, code, data):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    h.send_response(code)
    for k, v in cors().items():
        h.send_header(k, v)
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)

def safe_json(resp):
    """Parse JSON dengan fallback — tidak crash jika response bukan JSON."""
    try:
        text = resp.text.strip()
        if not text:
            raise ValueError("Response kosong (empty body)")
        # beberapa server IPTV wrap JSON dalam callback
        if text.startswith("//"):
            text = text[text.index("{"):]
        return json.loads(text)
    except Exception as e:
        ct = resp.headers.get("Content-Type", "")
        snippet = resp.text[:200].replace("\n", " ")
        raise ValueError(
            f"Bukan JSON valid (HTTP {resp.status_code}, Content-Type: {ct}). "
            f"Response awal: {snippet!r}"
        )

def norm_server(url):
    """Pastikan server URL tidak trailing slash."""
    return url.strip().rstrip("/")

def norm_portal(url):
    """Pastikan portal URL selalu berakhir /"""
    u = url.strip().rstrip("/") + "/"
    # beberapa portal pakai /c/ sebagai path terakhir sebelum portal.php
    # kalau user input http://host:port/c/ → keep as is
    # kalau user input http://host:port    → tambah /
    return u

def mac_session(portal, mac, token=None):
    s = requests.Session()
    s.verify = False
    s.headers.update({
        "User-Agent": MAG_UA,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": portal + "portal.php",
    })
    s.cookies.set("mac", mac)
    s.cookies.set("stb_lang", "en")
    s.cookies.set("timezone", "Europe/Amsterdam")
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s

# ─── handler ────────────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in cors().items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        send_json(self, 200, {"status": "ok", "service": "IPTV Proxy v9"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw)
        except Exception as e:
            send_json(self, 400, {"ok": False, "error": f"Bad JSON input: {e}"})
            return

        action = body.get("action", "")
        dispatch = {
            "handshake":    self._handshake,
            "get_channels": self._get_channels,
            "create_link":  self._create_link,
            "xtream_info":  self._xtream_info,
            "xtream_live":  self._xtream_live,
            "xtream_vod":   self._xtream_vod,
            "check_stream": self._check_stream,
            "fetch_m3u":    self._fetch_m3u,
        }
        fn = dispatch.get(action)
        if not fn:
            send_json(self, 400, {"ok": False, "error": f"Unknown action: {action}"})
            return
        try:
            fn(body)
        except Exception as e:
            send_json(self, 502, {"ok": False, "error": str(e)})

    # ── MAC / Stalker ────────────────────────────────────────────────────────

    def _handshake(self, body):
        portal = norm_portal(body.get("portal", ""))
        mac    = body.get("mac", "").strip().upper()
        s      = mac_session(portal, mac)

        r = s.get(
            f"{portal}portal.php?type=stb&action=handshake&JsHttpRequest=1-xml",
            timeout=TIMEOUT,
        )
        data  = safe_json(r)
        js    = data.get("js", {})
        token = js.get("token") if isinstance(js, dict) else None
        if token:
            s.headers["Authorization"] = f"Bearer {token}"

        profile = {}
        try:
            pr  = s.get(
                f"{portal}portal.php?type=account_info&action=get_main_info&JsHttpRequest=1-xml",
                timeout=TIMEOUT,
            )
            pjs = safe_json(pr).get("js", {})
            if isinstance(pjs, dict):
                fname = (pjs.get("fname","") + " " + pjs.get("lname","")).strip()
                profile = {
                    "name":   fname or "Unknown",
                    "expiry": pjs.get("phone","") or pjs.get("end_date","") or "Unlimited",
                }
        except Exception:
            pass

        send_json(self, 200, {"ok": True, "token": token, "profile": profile})

    def _get_channels(self, body):
        portal = norm_portal(body.get("portal",""))
        mac    = body.get("mac","").strip().upper()
        token  = body.get("token","")
        s      = mac_session(portal, mac, token)

        # try get_all_channels
        try:
            r  = s.get(f"{portal}portal.php?type=itv&action=get_all_channels&JsHttpRequest=1-xml", timeout=TIMEOUT)
            js = safe_json(r).get("js", {})
            if isinstance(js, dict) and js.get("data"):
                ch = js["data"]
                send_json(self, 200, {"ok": True, "channels": ch, "total": len(ch)})
                return
        except Exception:
            pass

        # fallback paginate
        all_ch, page = [], 1
        while True:
            r  = s.get(
                f"{portal}portal.php?type=itv&action=get_ordered_list&genre=*&p={page}&JsHttpRequest=1-xml",
                timeout=TIMEOUT,
            )
            js = safe_json(r).get("js", {})
            if not isinstance(js, dict): break
            data  = js.get("data", [])
            total = int(js.get("total_items", 0) or 0)
            if not data: break
            all_ch.extend(data)
            if total and len(all_ch) >= total: break
            if len(data) < 14: break
            page += 1

        send_json(self, 200, {"ok": True, "channels": all_ch, "total": len(all_ch)})

    def _create_link(self, body):
        portal = norm_portal(body.get("portal",""))
        mac    = body.get("mac","").strip().upper()
        token  = body.get("token","")
        cmd    = body.get("cmd","")
        s      = mac_session(portal, mac, token)

        cmd_enc = quote(str(cmd), safe=":/?&= #")
        r   = s.get(
            f"{portal}portal.php?type=itv&action=create_link&cmd={cmd_enc}&JsHttpRequest=1-xml",
            timeout=12,
        )
        js  = safe_json(r).get("js", {})
        url = ""
        if isinstance(js, dict):
            raw = str(js.get("cmd","") or js.get("url","")).strip()
            for part in reversed(raw.split()):
                if "://" in part:
                    url = part
                    break
        send_json(self, 200, {"ok": True, "url": url})

    # ── Xtream ───────────────────────────────────────────────────────────────

    def _xtream_info(self, body):
        server = norm_server(body.get("server",""))
        user   = body.get("user","")
        passwd = body.get("passwd","")

        # Coba dengan port 80 jika tidak ada port
        url = f"{server}/player_api.php?username={user}&password={passwd}"
        r   = requests.get(url, timeout=TIMEOUT, verify=False,
                           headers={"User-Agent": VLC_UA},
                           allow_redirects=True)
        data = safe_json(r)
        send_json(self, 200, {"ok": True, "data": data})

    def _xtream_live(self, body):
        server = norm_server(body.get("server",""))
        user   = body.get("user","")
        passwd = body.get("passwd","")
        h      = {"User-Agent": VLC_UA}

        # Ambil kategori dulu
        cats = {}
        try:
            cr = requests.get(
                f"{server}/player_api.php?username={user}&password={passwd}&action=get_live_categories",
                timeout=TIMEOUT, verify=False, headers=h, allow_redirects=True,
            )
            cats = {str(c["category_id"]): c["category_name"] for c in safe_json(cr)}
        except Exception:
            pass

        # Ambil streams
        r  = requests.get(
            f"{server}/player_api.php?username={user}&password={passwd}&action=get_live_streams",
            timeout=45, verify=False, headers=h, allow_redirects=True,
        )
        raw = safe_json(r)
        # raw bisa list langsung atau {"data": [...]}
        streams = raw if isinstance(raw, list) else raw.get("data", [])

        channels = []
        for ch in streams:
            cid = str(ch.get("category_id",""))
            channels.append({
                "name":      ch.get("name","Unknown"),
                "group":     cats.get(cid) or ch.get("category_name","Live TV"),
                "logo":      ch.get("stream_icon",""),
                "epg_id":    ch.get("epg_channel_id",""),
                "stream_id": ch.get("stream_id"),
                "num":       ch.get("num",""),
            })
        send_json(self, 200, {"ok": True, "channels": channels})

    def _xtream_vod(self, body):
        server = norm_server(body.get("server",""))
        user   = body.get("user","")
        passwd = body.get("passwd","")
        h      = {"User-Agent": VLC_UA}

        cats = {}
        try:
            cr = requests.get(
                f"{server}/player_api.php?username={user}&password={passwd}&action=get_vod_categories",
                timeout=TIMEOUT, verify=False, headers=h, allow_redirects=True,
            )
            cats = {str(c["category_id"]): c["category_name"] for c in safe_json(cr)}
        except Exception:
            pass

        r    = requests.get(
            f"{server}/player_api.php?username={user}&password={passwd}&action=get_vod_streams",
            timeout=45, verify=False, headers=h, allow_redirects=True,
        )
        raw  = safe_json(r)
        vods = raw if isinstance(raw, list) else raw.get("data", [])

        result = []
        for v in vods:
            cid = str(v.get("category_id",""))
            result.append({
                "name":      v.get("name","Unknown"),
                "group":     cats.get(cid,"VOD"),
                "logo":      v.get("stream_icon",""),
                "stream_id": v.get("stream_id"),
            })
        send_json(self, 200, {"ok": True, "channels": result})

    # ── Stream check ─────────────────────────────────────────────────────────

    def _check_stream(self, body):
        url = body.get("url","")
        if not url or "://" not in url:
            send_json(self, 200, {"ok": True, "alive": False, "reason": "No URL"})
            return
        try:
            hd = {"User-Agent": MAG_UA, "Connection": "close", "Accept": "*/*"}
            with requests.get(url, timeout=10, stream=True, headers=hd, verify=False) as r:
                if r.status_code not in (200, 206):
                    send_json(self, 200, {"ok": True, "alive": False, "reason": f"HTTP {r.status_code}"})
                    return
                ct = r.headers.get("Content-Type","").lower()
                if any(x in ct for x in ["text/html","application/json"]):
                    send_json(self, 200, {"ok": True, "alive": False, "reason": "HTML/JSON response"})
                    return
                chunk = r.raw.read(8192)
                alive = len(chunk) > 512
                send_json(self, 200, {"ok": True, "alive": alive, "reason": "OK" if alive else "Empty"})
        except Exception as e:
            send_json(self, 200, {"ok": True, "alive": False, "reason": str(e)[:100]})

    def _fetch_m3u(self, body):
        url = body.get("url","")
        r   = requests.get(url, timeout=25, verify=False,
                           headers={"User-Agent": VLC_UA},
                           allow_redirects=True)
        r.raise_for_status()
        content = r.text
        if "#EXTM3U" not in content and "extinf" not in content.lower()[:500]:
            send_json(self, 400, {"ok": False, "error": "Bukan file M3U/M3U8 valid"})
            return
        send_json(self, 200, {"ok": True, "content": content[:600000]})
