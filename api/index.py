from flask import Flask, request, Response, jsonify
import requests
import json

app = Flask(__name__)

@app.route('/api/convert', methods=['POST'])
def convert():
    body = request.get_json()
    portal = body.get('portal', '').rstrip('/') + '/'
    mac = body.get('mac', '').upper()
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C) MAG200',
        'X-Requested-With': 'XMLHttpRequest'
    })
    session.cookies.set('mac', mac)
    
    resp = session.get(f'{portal}portal.php?type=stb&action=handshake')
    data = resp.json()
    token = data.get('js', {}).get('token')
    if token:
        session.headers['Authorization'] = f'Bearer {token}'
    
    resp = session.get(f'{portal}portal.php?type=itv&action=get_all_channels')
    channels = resp.json().get('js', {}).get('data', [])
    
    lines = ['#EXTM3U']
    for ch in channels:
        name = ch.get('name', 'Unknown')
        cmd = ch.get('cmd', '')
        url = ''
        for part in cmd.split():
            if part.startswith(('http://', 'https://')):
                url = part
                break
        lines.append(f'#EXTINF:-1 tvg-name="{name}",{name}')
        lines.append(url or cmd)
    
    m3u = '\n'.join(lines)
    return Response(m3u, mimetype='application/x-mpegURL', 
                    headers={'Content-Disposition': 'attachment; filename="playlist.m3u"'})

@app.route('/api/validate', methods=['POST'])
def validate():
    body = request.get_json()
    m3u_text = body.get('m3u', '')
    
    urls = [line for line in m3u_text.splitlines() if line.startswith(('http://', 'https://'))]
    
    results = []
    for url in urls[:50]:  # Batasi 50 utk cepat
        try:
            r = requests.get(url, timeout=5, stream=True)
            status = 'live' if r.status_code == 200 else 'dead'
        except:
            status = 'dead'
        results.append({'url': url, 'status': status})
    
    live_count = sum(1 for r in results if r['status'] == 'live')
    return jsonify({'total': len(results), 'live': live_count, 
                    'dead': len(results)-live_count, 'results': results})

@app.route('/')
def home():
    return jsonify({'message': 'M3U Converter API', 'endpoints': ['/api/convert', '/api/validate']})

# Untuk Vercel
app = app
