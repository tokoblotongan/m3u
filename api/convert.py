"""
IPTV Convert API v9-fix — menghasilkan file M3U dari Xtream atau MAC.
Fix: robust JSON parsing, handle redirect, better error messages.
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
VLC_UA  = "VLC/3.0.18 LibVLC/3.0.18"
TIMEOUT = 20

XXX_KEYWORDS = [
    "xxx","adult","porn","sex","erotic","18+","xvideos","xnxx",
    "brazzers","playboy","penthouse","nude","naked","milf","anal",
    "hardcore","hentai","redtube","pornhub","granny","mature",
    "fetish","bdsm","shemale","cam4","chaturbate",
]

# ─── helpers ────────────────────────────────────────────────────────────────

def cors():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

def safe_json(resp):
    try:
        text = resp.text.strip()
        if not text:
            raise ValueError("Response kosong")
        if text.startswith("//"):
            text = text[text.index("{"):]
        return json.loads(text)
    except Exception as e:
        ct      = resp.headers.get("Content-Type","")
        snippet = resp.text[:300].replace("\n"," ")
        raise ValueError(f"Bukan JSON (HTTP {resp.status_code}, {ct}): {snippet!r}")

def is_xxx(name, group=""):
    c = (str(name) + " " + str(group)).lower()
    return any(k in c for k in XXX_KEYWORDS)

def extract_cmd_url(cmd):
    if not cmd: return ""
    for part in reversed(str(cmd).split()):
        if part.startswith(("http://","https://","rtmp://","rtmpe://")):
            return part
    return str(cmd).strip() if str(cmd).strip().startswith("http") else ""

def norm_server(url):
    return url.strip().rstrip("/")

def norm_portal(url):
    return url.strip().rstrip("/") + "/"

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

def build_m3u(entries, epg_url="", include_xxx=False):
    lines = ["#EXTM3U" + (f' x-tvg-url="{epg_url}"' if epg_url else "")]
    for e in entries:
        grp  = e.get("group","")
        name = e.get("name","Unknown")
        if is_xxx(name, grp) and not include_xxx:
            continue
        sid = e.get("stream_id")
        tpl = e.get("url_tpl","")
        url = tpl.format(sid=sid) if (sid is not None and tpl) else e.get("url","")
        if not url:
            continue
        line = "#EXTINF:-1"
        if e.get("epg_id"): line += f' tvg-id="{e["epg_id"]}"'
        line += f' tvg-name="{name}"'
        if e.get("logo"):   line += f' tvg-logo="{e["logo"]}"'
        if grp:             line += f' group-title="{grp}"'
        if e.get("num"):    line += f' tvg-chno="{e["num"]}"'
        line += f",{name}"
        lines.append(line)
        lines.append(url)
    return "\n".join(lines)

# ─── main handler ───────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_OPTIONS(self):
        self.send_response(204)
        for k,v in cors().items(): self.send_header(k,v)
        self.end_headers()

    def do_GET(self):
        self._send_json(200, {"status":"ok","service":"IPTV Convert API v9"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length",0))
            body   = json.loads(self.rfile.read(length) if length else b"{}")
        except Exception as e:
            self._send_json(400, {"ok":False,"error":f"Bad JSON: {e}"}); return

        mode = body.get("mode","")
        try:
            if   mode == "xtream": self._convert_xtream(body)
            elif mode == "mac":    self._convert_mac(body)
            else: self._send_json(400, {"ok":False,"error":"mode harus 'xtream' atau 'mac'"})
        except Exception as e:
            self._send_json(500, {"ok":False,"error":str(e)})

    def _send_json(self, code, data):
        b = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        for k,v in cors().items(): self.send_header(k,v)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def _send_m3u(self, content, filename="playlist.m3u"):
        b = content.encode("utf-8")
        self.send_response(200)
        for k,v in cors().items(): self.send_header(k,v)
        self.send_header("Content-Type","audio/x-mpegurl")
        self.send_header("Content-Disposition",f'attachment; filename="{filename}"')
        self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)

    # ── Xtream ───────────────────────────────────────────────────────────────

    def _convert_xtream(self, body):
        server  = norm_server(body.get("server",""))
        user    = body.get("user","")
        passwd  = body.get("passwd","")
        inc_live= body.get("live", True)
        inc_vod = body.get("vod",  False)
        inc_xxx = body.get("xxx",  False)
        epg_url = body.get("epg","")
        fmt     = body.get("fmt","ts")
        fname   = body.get("filename","playlist.m3u")
        h       = {"User-Agent": VLC_UA}
        entries = []

        if inc_live or inc_xxx:
            cats = {}
            try:
                cr   = requests.get(f"{server}/player_api.php?username={user}&password={passwd}&action=get_live_categories",
                                    timeout=TIMEOUT, verify=False, headers=h, allow_redirects=True)
                cats = {str(c["category_id"]): c["category_name"] for c in safe_json(cr)}
            except Exception: pass

            r   = requests.get(f"{server}/player_api.php?username={user}&password={passwd}&action=get_live_streams",
                               timeout=45, verify=False, headers=h, allow_redirects=True)
            raw = safe_json(r)
            streams = raw if isinstance(raw, list) else raw.get("data",[])
            for ch in streams:
                cid = str(ch.get("category_id",""))
                grp = cats.get(cid) or ch.get("category_name","Live TV")
                xxx = is_xxx(ch.get("name",""), grp)
                if xxx and not inc_xxx:   continue
                if not xxx and not inc_live: continue
                entries.append({
                    "name":      ch.get("name","Unknown"),
                    "group":     grp,
                    "logo":      ch.get("stream_icon",""),
                    "epg_id":    ch.get("epg_channel_id",""),
                    "num":       ch.get("num",""),
                    "stream_id": ch.get("stream_id"),
                    "url_tpl":   f"{server}/live/{user}/{passwd}/{{sid}}.{fmt}",
                })

        if inc_vod:
            cats = {}
            try:
                cr   = requests.get(f"{server}/player_api.php?username={user}&password={passwd}&action=get_vod_categories",
                                    timeout=TIMEOUT, verify=False, headers=h, allow_redirects=True)
                cats = {str(c["category_id"]): c["category_name"] for c in safe_json(cr)}
            except Exception: pass

            r   = requests.get(f"{server}/player_api.php?username={user}&password={passwd}&action=get_vod_streams",
                               timeout=45, verify=False, headers=h, allow_redirects=True)
            raw = safe_json(r)
            vods = raw if isinstance(raw, list) else raw.get("data",[])
            for v in vods:
                cid = str(v.get("category_id",""))
                entries.append({
                    "name":      v.get("name","Unknown"),
                    "group":     cats.get(cid,"VOD"),
                    "logo":      v.get("stream_icon",""),
                    "epg_id":    "",
                    "num":       "",
                    "stream_id": v.get("stream_id"),
                    "url_tpl":   f"{server}/movie/{user}/{passwd}/{{sid}}.{fmt}",
                })

        m3u = build_m3u(entries, epg_url=epg_url, include_xxx=True)
        self._send_m3u(m3u, fname)

    # ── MAC ──────────────────────────────────────────────────────────────────

    def _convert_mac(self, body):
        portal       = norm_portal(body.get("portal",""))
        mac          = body.get("mac","").strip().upper()
        resolve_mode = body.get("resolve_mode","cmd")  # resolve | cmd | raw
        inc_xxx      = body.get("xxx", False)
        epg_url      = body.get("epg","")
        fmt          = body.get("fmt","ts")
        fname        = body.get("filename","playlist.m3u")

        # handshake
        s = mac_session(portal, mac)
        r = s.get(f"{portal}portal.php?type=stb&action=handshake&JsHttpRequest=1-xml", timeout=TIMEOUT)
        js = safe_json(r).get("js",{})
        token = js.get("token") if isinstance(js,dict) else None
        if token: s.headers["Authorization"] = f"Bearer {token}"

        # get channels
        ch_list = []
        try:
            r  = s.get(f"{portal}portal.php?type=itv&action=get_all_channels&JsHttpRequest=1-xml", timeout=TIMEOUT)
            js = safe_json(r).get("js",{})
            if isinstance(js,dict) and js.get("data"):
                ch_list = js["data"]
        except Exception: pass

        if not ch_list:
            page = 1
            while True:
                try:
                    r  = s.get(f"{portal}portal.php?type=itv&action=get_ordered_list&genre=*&p={page}&JsHttpRequest=1-xml", timeout=TIMEOUT)
                    js = safe_json(r).get("js",{})
                    if not isinstance(js,dict): break
                    data  = js.get("data",[])
                    total = int(js.get("total_items",0) or 0)
                    if not data: break
                    ch_list.extend(data)
                    if total and len(ch_list) >= total: break
                    if len(data) < 14: break
                    page += 1
                except Exception: break

        entries = []
        for obj in ch_list:
            grp  = obj.get("genre_name") or obj.get("category_name") or str(obj.get("tv_genre_id","")) or "MAC TV"
            name = obj.get("name","Unknown")
            cmd  = obj.get("cmd","")

            if is_xxx(name, grp) and not inc_xxx:
                continue

            if resolve_mode == "resolve":
                url = ""
                try:
                    enc = quote(str(cmd), safe=":/?&= #")
                    lr  = s.get(f"{portal}portal.php?type=itv&action=create_link&cmd={enc}&JsHttpRequest=1-xml", timeout=10)
                    ljs = safe_json(lr).get("js",{})
                    if isinstance(ljs,dict):
                        raw = str(ljs.get("cmd","") or ljs.get("url","")).strip()
                        for part in reversed(raw.split()):
                            if "://" in part: url = part; break
                except Exception: pass
                if not url: url = extract_cmd_url(cmd)
            elif resolve_mode == "cmd":
                url = extract_cmd_url(cmd)
            else:
                url = str(cmd).strip() if cmd else ""

            entries.append({
                "name":   name,
                "group":  grp,
                "logo":   obj.get("logo",""),
                "epg_id": obj.get("xmltv_id",""),
                "num":    obj.get("number",""),
                "stream_id": None,
                "url":    url,
            })

        m3u = build_m3u(entries, epg_url=epg_url, include_xxx=True)
        self._send_m3u(m3u, fname)
