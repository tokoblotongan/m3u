from flask import Flask, request, Response, jsonify
import requests
import json
import re
from urllib.parse import quote

app = Flask(__name__)

# ==================== HOME ====================
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'message': 'M3U Converter API',
        'endpoints': ['/api/convert', '/api/validate'],
        'status': 'online'
    })

# ==================== CONVERT STALKER TO M3U ====================
@app.route('/api/convert', methods=['POST', 'GET'])
def convert():
    if request.method == 'GET':
        return jsonify({
            'message': 'Gunakan POST method dengan JSON body',
            'example': {
                'portal': 'http://your-portal.com:8080/c/',
                'mac': '00:1A:79:12:34:56',
                'types': ['live']
            }
        })
    
    try:
        body = request.get_json()
        if not body:
            return jsonify({'error': 'JSON body required'}), 400
        
        portal = body.get('portal', '').rstrip('/') + '/'
        mac = body.get('mac', '').upper()
        
        if not portal or not mac:
            return jsonify({'error': 'portal and mac required'}), 400
        
        # MAC address validation
        if not re.match(r'^([0-9A-F]{2}[:-]){5}[0-9A-F]{2}$', mac):
            return jsonify({'error': 'Invalid MAC format. Use 00:1A:79:XX:XX:XX'}), 400
        
        # Connect to Stalker portal
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C) MAG200 stbapp ver: 2',
            'X-Requested-With': 'XMLHttpRequest'
        })
        session.cookies.set('mac', mac)
        
        # Handshake
        try:
            resp = session.get(f'{portal}portal.php?type=stb&action=handshake', timeout=10)
            data = resp.json()
            token = data.get('js', {}).get('token')
            if token:
                session.headers['Authorization'] = f'Bearer {token}'
        except Exception as e:
            return jsonify({'error': f'Handshake failed: {str(e)}'}), 500
        
        # Get channels
        try:
            resp = session.get(f'{portal}portal.php?type=itv&action=get_all_channels', timeout=15)
            channels = resp.json().get('js', {}).get('data', [])
        except:
            # Fallback to paginated method
            all_channels = []
            page = 1
            while True:
                resp = session.get(f'{portal}portal.php?type=itv&action=get_ordered_list&genre=*&p={page}', timeout=15)
                data = resp.json().get('js', {})
                page_channels = data.get('data', [])
                if not page_channels:
                    break
                all_channels.extend(page_channels)
                page += 1
            channels = all_channels
        
        if not channels:
            return jsonify({'error': 'No channels found'}), 404
        
        # Build M3U
        lines = ['#EXTM3U']
        for ch in channels:
            name = ch.get('name', 'Unknown')
            cmd = ch.get('cmd', '')
            
            # Extract URL from cmd
            url = ''
            for part in cmd.split():
                if part.startswith(('http://', 'https://', 'rtmp://')):
                    url = part
                    break
            
            if not url:
                url = cmd
            
            # Add channel info
            genre = ch.get('genre_name', ch.get('category_name', 'IPTV'))
            logo = ch.get('logo', '')
            epg_id = ch.get('xmltv_id', ch.get('epg_id', ''))
            ch_num = ch.get('number', ch.get('num', ''))
            
            extinf = f'#EXTINF:-1'
            if epg_id:
                extinf += f' tvg-id="{epg_id}"'
            if name:
                extinf += f' tvg-name="{name}"'
            if logo:
                extinf += f' tvg-logo="{logo}"'
            if genre:
                extinf += f' group-title="{genre}"'
            if ch_num:
                extinf += f' tvg-chno="{ch_num}"'
            extinf += f',{name}'
            
            lines.append(extinf)
            lines.append(url if url else '# No URL found')
        
        m3u_content = '\n'.join(lines)
        
        return Response(
            m3u_content,
            mimetype='application/x-mpegURL',
            headers={
                'Content-Disposition': f'attachment; filename="playlist_{mac.replace(":", "")}.m3u"',
                'Content-Type': 'application/x-mpegURL; charset=utf-8'
            }
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== VALIDATE M3U ====================
@app.route('/api/validate', methods=['POST', 'GET'])
def validate():
    if request.method == 'GET':
        return jsonify({
            'message': 'POST method: kirim M3U URL atau text untuk cek channel live/dead',
            'example': {'m3u': 'https://example.com/playlist.m3u', 'timeout': 5}
        })
    
    try:
        body = request.get_json()
        m3u_source = body.get('m3u', '')
        timeout = min(body.get('timeout', 5), 10)
        
        if not m3u_source:
            return jsonify({'error': 'm3u parameter required (URL or text)'}), 400
        
        # Get M3U content
        if m3u_source.startswith(('http://', 'https://')):
            resp = requests.get(m3u_source, timeout=15)
            content = resp.text
        else:
            content = m3u_source
        
        # Parse M3U
        channels = []
        current = {'name': 'Unknown'}
        
        for line in content.splitlines():
            line = line.strip()
            if line.startswith('#EXTINF'):
                # Extract name
                if ',' in line:
                    current['name'] = line.split(',')[-1].strip()
                # Extract group
                group_match = re.search(r'group-title="([^"]*)"', line)
                current['group'] = group_match.group(1) if group_match else 'Other'
                # Check if XXX
                xxx_keywords = ['xxx', 'adult', 'porn', 'sex', '18+', 'erotic', 'brazzers', 'playboy']
                current['xxx'] = any(k in current['name'].lower() for k in xxx_keywords)
            elif line.startswith(('http://', 'https://')):
                current['url'] = line
                channels.append(current.copy())
                current = {'name': 'Unknown', 'group': 'Other', 'xxx': False}
        
        # Check each channel (limit to 50 for performance)
        results = []
        live_count = 0
        dead_count = 0
        
        for ch in channels[:50]:
            try:
                r = requests.get(ch['url'], timeout=timeout, stream=True)
                if r.status_code in [200, 206]:
                    status = 'live'
                    live_count += 1
                else:
                    status = 'dead'
                    dead_count += 1
            except:
                status = 'dead'
                dead_count += 1
            
            results.append({
                'name': ch['name'],
                'url': ch['url'],
                'status': status,
                'xxx': ch.get('xxx', False),
                'group': ch.get('group', 'Other')
            })
        
        return jsonify({
            'total': len(channels),
            'checked': len(results),
            'live': live_count,
            'dead': dead_count,
            'xxx_count': sum(1 for r in results if r['xxx']),
            'results': results
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== TEST PORTAL ====================
@app.route('/api/test', methods=['GET'])
def test_portal():
    portal = request.args.get('portal', '')
    if not portal:
        return jsonify({'error': 'portal parameter required'}), 400
    
    try:
        r = requests.get(portal, timeout=10)
        return jsonify({
            'ok': r.status_code == 200,
            'status': r.status_code,
            'portal': portal
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
