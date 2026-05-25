import requests
from concurrent.futures import ThreadPoolExecutor

def check_url(url):
    try:
        r = requests.get(url, timeout=5, stream=True)
        if r.status_code == 200:
            return 'live'
        return 'dead'
    except:
        return 'dead'

def handler(request):
    if request.method == 'POST':
        import json
        body = json.loads(request.body)
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
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'total': len(results),
                'live': live_count,
                'dead': len(results) - live_count,
                'results': results
            })
        }
    
    return {'statusCode': 405, 'body': 'Method Not Allowed'}
