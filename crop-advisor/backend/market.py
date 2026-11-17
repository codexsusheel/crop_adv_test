"""Server-side data.gov.in adapter. The browser never receives the API key."""
import os
import time
import math
from datetime import datetime, timezone
import httpx

RESOURCE = '9ef84268-d588-465a-a308-a864a43d0070'
SOURCE = 'https://www.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi'
CACHE = {}
# Only unambiguous names are automatic; processing form/variety matters for prices.
COMMODITIES = {'rice': 'Rice', 'maize': 'Maize', 'cotton': 'Cotton', 'apple': 'Apple',
    'banana': 'Banana', 'grapes': 'Grapes', 'mango': 'Mango', 'orange': 'Orange',
    'papaya': 'Papaya', 'pomegranate': 'Pomegranate', 'watermelon': 'Water Melon',
    'muskmelon': 'Musk Melon', 'coconut': 'Coconut', 'jute': 'Jute'}

async def prices(crop, state, commodity=None, district=None):
    commodity = commodity or COMMODITIES.get(crop)
    base = {'crop': crop, 'source_url': SOURCE, 'unit': 'INR/quintal; verify the quoted commodity and variety',
            'state': state, 'commodity': commodity}
    if not commodity:
        return {**base, 'status': 'needs_commodity', 'records': [],
                'message': 'Enter the exact mandi commodity name; no processing-form conversion is assumed.'}
    key = (commodity, state, district)
    cached = CACHE.get(key)
    if cached and time.time() - cached[0] < 21600:
        return {**cached[1], 'status': 'cached', 'cache_age_seconds': round(time.time()-cached[0])}
    api_key = os.getenv('DATA_GOV_API_KEY')
    if not api_key:
        return {**base, 'status': 'unavailable', 'records': [], 'message': 'Set DATA_GOV_API_KEY on the server to enable live prices. No reference price has been invented.'}
    params = {'api-key': api_key, 'format': 'json', 'limit': 100, 'offset': 0,
              'filters[commodity]': commodity, 'filters[state]': state}
    if district:
        params['filters[district]'] = district
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f'https://api.data.gov.in/resource/{RESOURCE}', params=params)
            response.raise_for_status()
            data = response.json()
        if not isinstance(data.get('records'), list):
            raise ValueError('Unexpected provider response')
        records = []
        for row in data['records']:
            # Defensive exact filtering prevents displaying a different location's quote.
            if row.get('state', '').casefold() != state.casefold() or row.get('commodity', '').casefold() != commodity.casefold():
                continue
            if district and row.get('district', '').casefold() != district.casefold():
                continue
            try:
                modal = float(row['modal_price'])
                if not math.isfinite(modal) or modal <= 0:
                    continue
            except (ValueError, TypeError, KeyError):
                continue
            records.append({k: row.get(k) for k in ('state','district','market','commodity','variety','grade','arrival_date','min_price','max_price','modal_price')})
        result = {**base, 'status': 'live' if records else 'no_data', 'records': records,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'message': 'Up to 100 matching quotes; use arrival_date for freshness. Current prices are not harvest-price forecasts.',
            'provider_total': data.get('total')}
        if records:
            CACHE[key] = (time.time(), result)
        return result
    except (httpx.HTTPError, ValueError, TypeError):
        # Do not return exception URLs: they can contain the API key.
        return {**base, 'status': 'unavailable', 'records': [], 'message': 'Market service unavailable. Retry later or enter a verified price in the profit calculator.'}
