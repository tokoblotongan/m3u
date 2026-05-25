"""
IPTV Convert API — menghasilkan file M3U dari Xtream atau MAC portal.
"""
import json
import re
import requests
import urllib3
from http.server import BaseHTTPRequestHandler
from urllib.parse import quote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAG_UA = (
    "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 "
    "(KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3"
)
XXX_KEYWORDS = [
    "xxx", "adult", "porn", "sex", "erotic", "18+", "xvideos", "xnxx",
    "brazzers", "playboy", "penthouse", "nude", "naked", "milf", "anal",
    "hardcore", "hentai", "redtube", "pornhub", "granny", "mature",
    "fetish", "bdsm", "shemale", "cam4", "chaturbate",
]

def is_xxx(name, group=""):
    combined = (str(name) + " " + str(group)).lower()
    return any(k in combined for k in XXX_KEYWORDS)

def extract_cmd_url(cmd):
    if not cmd:
        return ""
    cmd = str(cmd).strip()
    for part in reversed(cmd.split()):
        if part.startswith(("http://", "https://", "rtmp://", "rtmpe://")):
            return part
    if cmd.startswith(("http://", "https://", "rtmp://")):
        return cmd
    return cmd

def mac_session(portal, mac, token=None):
    s = requests.Session()
    s.verify = False
    s.headers.update({
        "User-Agent": MAG_UA,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{portal}portal.php",
    })
    s.cookies.update({"mac": mac, "stb_lang": "en", "timezone": "Europe/Amsterdam"})
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s

def build_m3u(entries, epg_url="", include_xxx=False, fmt="ts"):
    lines = ["#EXTM3U" + (f' x-tvg-url="{epg_url}"' if epg_url else "")]
    for e in entries:
        grp = e.get("group", "")
        name = e.get("name", "Unknown")
        if is_xxx(name, grp) and not include_xxx:
            continue
        sid = e.get("stream_id")
        tpl = e.get("url_tpl", "")
        if sid is not None and tpl:
            url = tpl.format(sid=sid)
        else:
            url = e.get("url", "")
        if not url:
            continue
        ext_line = "#EXTINF:-1"
        if e.get("epg_id"):
            ext_line += f' tvg-id="{e["epg_id"]}"'
        ext_line += f' tvg-name="{name}"'
        if e.get("logo"):
            ext_line += f' tvg-logo="{e["logo"]}"'
        if grp:
            ext_line += f' group-title="{grp}"'
        if e.get("num"):
            ext_line += f' tvg-chno="{e["num"]}"'
        ext_line += f",{name}"
        lines.append(ext_line)
        lines.append(url)
    return "\n".join(lines)


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
        body = json.dumps({"status": "ok", "service": "IPTV Convert API v9"}).encode()
        self.send_response(200)
        for k, v in self._cors().items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) if length else b"{}")
        except Exception as e:
            self._err(400, f"Bad JSON: {e}")
            return

        mode = body.get("mode", "")
        try:
            if mode == "xtream":
                self._convert_xtream(body)
            elif mode == "mac":
                self._convert_mac(body)
            else:
                self._err(400, "mode harus 'xtream' atau 'mac'")
        except Exception as e:
            self._err(500, str(e))

    def _err(self, code, msg):
        b = json.dumps({"ok": False, "error": msg}).encode()
        self.send_response(code)
        for k, v in self._cors().items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _send_m3u(self, content, filename="playlist.m3u"):
        b = content.encode("utf-8")
        self.send_response(200)
        for k, v in self._cors().items():
            self.send_header(k, v)
        self.send_header("Content-Type", "audio/x-mpegurl")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _convert_xtream(self, body):
        server = body.get("server", "").rstrip("/")
        user = body.get("user", "")
        passwd = body.get("passwd", "")
        include_live = body.get("live", True)
        include_vod = body.get("vod", False)
        include_xxx = body.get("xxx", False)
        epg_url = body.get("epg", "")
        fmt = body.get("fmt", "ts")
        filename = body.get("filename", "playlist.m3u")

        h = {"User-Agent": "VLC/3.0.18 LibVLC/3.0.18"}
        entries = []

        if include_live or include_xxx:
            cats = {}
            try:
                cr = requests.get(
                    f"{server}/player_api.php?username={user}&password={passwd}&action=get_live_categories",
                    timeout=15, verify=False, headers=h,
                )
                cats = {str(c["category_id"]): c["category_name"] for c in cr.json()}
            except Exception:
                pass
            r = requests.get(
                f"{server}/player_api.php?username={user}&password={passwd}&action=get_live_streams",
                timeout=30, verify=False, headers=h,
            )
            for ch in r.json():
                cid = str(ch.get("category_id", ""))
                grp = cats.get(cid) or ch.get("category_name", "Live TV")
                xxx = is_xxx(ch.get("name", ""), grp)
                if xxx and not include_xxx:
                    continue
                if not xxx and not include_live:
                    continue
                entries.append({
                    "name": ch.get("name", "Unknown"),
                    "group": grp,
                    "logo": ch.get("stream_icon", ""),
                    "epg_id": ch.get("epg_channel_id", ""),
                    "num": ch.get("num", ""),
                    "stream_id": ch.get("stream_id"),
                    "url_tpl": f"{server}/live/{user}/{passwd}/{{sid}}.{fmt}",
                })

        if include_vod:
            cats = {}
            try:
                cr = requests.get(
                    f"{server}/player_api.php?username={user}&password={passwd}&action=get_vod_categories",
                    timeout=15, verify=False, headers=h,
                )
                cats = {str(c["category_id"]): c["category_name"] for c in cr.json()}
            except Exception:
                pass
            r = requests.get(
                f"{server}/player_api.php?username={user}&password={passwd}&action=get_vod_streams",
                timeout=30, verify=False, headers=h,
            )
            for v in r.json():
                cid = str(v.get("category_id", ""))
                entries.append({
                    "name": v.get("name", "Unknown"),
                    "group": cats.get(cid, "VOD"),
                    "logo": v.get("stream_icon", ""),
                    "epg_id": "",
                    "num": "",
                    "stream_id": v.get("stream_id"),
                    "url_tpl": f"{server}/movie/{user}/{passwd}/{{sid}}.{fmt}",
                })

        m3u = build_m3u(entries, epg_url=epg_url, include_xxx=True, fmt=fmt)
        self._send_m3u(m3u, filename)

    def _convert_mac(self, body):
        portal = body.get("portal", "").rstrip("/") + "/"
        mac = body.get("mac", "").strip().upper()
        resolve_mode = body.get("resolve_mode", "cmd")  # resolve | cmd | raw
        include_xxx = body.get("xxx", False)
        epg_url = body.get("epg", "")
        fmt = body.get("fmt", "ts")
        filename = body.get("filename", "playlist.m3u")

        # Auth
        s = mac_session(portal, mac)
        r = s.get(
            f"{portal}portal.php?type=stb&action=handshake&JsHttpRequest=1-xml",
            timeout=15,
        )
        js = r.json().get("js", {})
        token = js.get("token") if isinstance(js, dict) else None
        if token:
            s.headers["Authorization"] = f"Bearer {token}"

        # Get channels
        ch_list = []
        try:
            r = s.get(
                f"{portal}portal.php?type=itv&action=get_all_channels&JsHttpRequest=1-xml",
                timeout=15,
            )
            js = r.json().get("js", {})
            if isinstance(js, dict) and js.get("data"):
                ch_list = js["data"]
        except Exception:
            pass

        if not ch_list:
            page = 1
            while True:
                try:
                    r = s.get(
                        f"{portal}portal.php?type=itv&action=get_ordered_list"
                        f"&genre=*&p={page}&JsHttpRequest=1-xml",
                        timeout=15,
                    )
                    js = r.json().get("js", {})
                    if not isinstance(js, dict):
                        break
                    data = js.get("data", [])
                    total = int(js.get("total_items", 0))
                    if not data:
                        break
                    ch_list.extend(data)
                    if total and len(ch_list) >= total:
                        break
                    if len(data) < 14:
                        break
                    page += 1
                except Exception:
                    break

        # Build entries
        entries = []
        for obj in ch_list:
            grp = (
                obj.get("genre_name") or obj.get("category_name") or
                str(obj.get("tv_genre_id", "")) or "MAC TV"
            )
            name = obj.get("name", "Unknown")
            cmd = obj.get("cmd", "")

            if is_xxx(name, grp) and not include_xxx:
                continue

            if resolve_mode == "resolve":
                url = ""
                try:
                    cmd_encoded = quote(str(cmd), safe=":/?&= #")
                    lr = s.get(
                        f"{portal}portal.php?type=itv&action=create_link"
                        f"&cmd={cmd_encoded}&JsHttpRequest=1-xml",
                        timeout=8,
                    )
                    ljs = lr.json().get("js", {})
                    if isinstance(ljs, dict):
                        raw = str(ljs.get("cmd", "") or ljs.get("url", "")).strip()
                        for part in reversed(raw.split()):
                            if "://" in part:
                                url = part
                                break
                except Exception:
                    pass
                if not url:
                    url = extract_cmd_url(cmd)
            elif resolve_mode == "cmd":
                url = extract_cmd_url(cmd)
            else:
                url = str(cmd).strip() if cmd else ""

            entries.append({
                "name": name,
                "group": grp,
                "logo": obj.get("logo", ""),
                "epg_id": obj.get("xmltv_id", ""),
                "num": obj.get("number", ""),
                "stream_id": None,
                "url": url,
            })

        m3u = build_m3u(entries, epg_url=epg_url, include_xxx=True, fmt=fmt)
        self._send_m3u(m3u, filename)
