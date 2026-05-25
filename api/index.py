import requests
import json
from urllib.parse import quote

def handler(request):
    if request.method == 'POST':
        body = json.loads(request.body)
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
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/x-mpegURL',
                'Content-Disposition': 'attachment; filename="playlist.m3u"'
            },
            'body': m3u
        }
    
    return {'statusCode': 405, 'body': 'Method Not Allowed'}
