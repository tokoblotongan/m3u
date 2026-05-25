from http.server import BaseHTTPRequestHandler
import requests
import json
from concurrent.futures import ThreadPoolExecutor

def check_url(url):
    try:
        r = requests.get(url, timeout=5, stream=True)
        if r.status_code == 200:
            return 'live'
        return 'dead'
    except:
        return 'dead'

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        body = json.loads(post_data.decode('utf-8'))
        
        m3u_text = body.get('m3u', '')
        
        # Parse M3U sederhana
        urls = []
        for line in m3u_text.splitlines():
            if line.startswith(('http://', 'https://')):
                urls.append(line)
        
        # Cek paralel
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(check_url, url): url for url in urls[:100]}
            for future in futures:
                results.append({'url': futures[future], 'status': future.result()})
        
        live_count = sum(1 for r in results if r['status'] == 'live')
        
        response = {
            'total': len(results),
            'live': live_count,
            'dead': len(results) - live_count,
            'results': results
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))
        return
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'ok', 'message': 'M3U Validator API'}).encode('utf-8'))
