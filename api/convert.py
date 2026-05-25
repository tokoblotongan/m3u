from http.server import BaseHTTPRequestHandler
import requests
import json
from urllib.parse import quote

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        body = json.loads(post_data.decode('utf-8'))
        
        portal = body.get('portal', '').rstrip('/') + '/'
        mac = body.get('mac', '').upper()
        
        # Auth ke Stalker portal
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C) MAG200',
            'X-Requested-With': 'XMLHttpRequest'
        })
        session.cookies.set('mac', mac)
        
        # Handshake
        resp = session.get(f'{portal}portal.php?type=stb&action=handshake')
        data = resp.json()
        token = data.get('js', {}).get('token')
        if token:
            session.headers['Authorization'] = f'Bearer {token}'
        
        # Ambil channel
        resp = session.get(f'{portal}portal.php?type=itv&action=get_all_channels')
        channels = resp.json().get('js', {}).get('data', [])
        
        # Build M3U
        lines = ['#EXTM3U']
        for ch in channels:
            name = ch.get('name', 'Unknown')
            cmd = ch.get('cmd', '')
            # Extract URL dari cmd
            url = ''
            for part in cmd.split():
                if part.startswith(('http://', 'https://')):
                    url = part
                    break
            
            lines.append(f'#EXTINF:-1 tvg-name="{name}" group-title="IPTV",{name}')
            lines.append(url or cmd)
        
        m3u = '\n'.join(lines)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-mpegURL')
        self.send_header('Content-Disposition', 'attachment; filename="playlist.m3u"')
        self.end_headers()
        self.wfile.write(m3u.encode('utf-8'))
        return
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<h1>M3U Converter API</h1><p>Use POST method with portal and mac parameters</p>')
