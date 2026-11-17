"""One-shot diagnostic. Reads a pasted request privately; never saves its key."""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import httpx

text = Path(sys.argv[1]).read_text(encoding='utf-8-sig')
url = re.search(r'https://api\.data\.gov\.in/[^\s\x27]+', text).group()
parsed = urlparse(url)
key = parse_qs(parsed.query)['api-key'][0]
endpoint = f'https://api.data.gov.in{parsed.path}'
params = {'api-key': key, 'format': 'json', 'limit': 2,
          'filters[State]': 'Telangana', 'filters[District]': 'Hyderabad',
          'filters[Commodity]': 'Apple', 'filters[Arrival_Date]': '16-11-2026'}

def check(item):
    label, query = item
    start = time.monotonic()
    try:
        response = httpx.get(endpoint, params=query,
                             timeout=httpx.Timeout(45, connect=10))
        body = response.json()
        return {'request': label, 'http': response.status_code,
                'seconds': round(time.monotonic()-start, 1),
                'status': body.get('status'), 'count': body.get('count')}
    except httpx.HTTPError as error:
        return {'request': label, 'error': type(error).__name__,
                'seconds': round(time.monotonic()-start, 1)}
    except (ValueError, AttributeError):
        return {'request': label, 'error': 'Non-JSON or unexpected response'}

with ThreadPoolExecutor(max_workers=2) as pool:
    for result in pool.map(check, [('minimal', {'api-key': key, 'format': 'json', 'limit': 1}),
                                   ('filtered', params)]):
        print(json.dumps(result), flush=True)
