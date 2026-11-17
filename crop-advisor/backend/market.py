"""Server-side data.gov.in adapter. The browser never receives the API key."""
import os
import time
import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import httpx

RESOURCE = '35985678-0d79-46b4-9ed6-6f13308a1d24'
SOURCE = 'https://www.data.gov.in/resource/variety-wise-daily-market-prices-data-commodity'
CACHE = {}
READ_TIMEOUT_SECONDS = 45
# Only unambiguous names are automatic; processing form/variety matters for prices.
COMMODITIES = {'rice': 'Rice', 'maize': 'Maize', 'cotton': 'Cotton', 'apple': 'Apple',
    'banana': 'Banana', 'grapes': 'Grapes', 'mango': 'Mango', 'orange': 'Orange',
    'papaya': 'Papaya', 'pomegranate': 'Pomegranate', 'watermelon': 'Water Melon',
    'muskmelon': 'Musk Melon', 'coconut': 'Coconut', 'jute': 'Jute'}

async def prices(crop, state, commodity=None, district=None, arrival_date=None):
    commodity = commodity or COMMODITIES.get(crop)
    state = state.strip()
    district = (district or '').strip()
    requested_date = arrival_date or datetime.now(ZoneInfo('Asia/Kolkata')).date()
    base = {'crop': crop, 'source_url': SOURCE, 'unit': 'INR/quintal; verify the quoted commodity and variety',
            'state': state, 'commodity': commodity, 'district': district,
            'requested_date': requested_date.isoformat(), 'resource_id': RESOURCE}
    def failure(code, message, upstream_status=None):
        # Never expose provider exception text or request URLs (contain the key).
        return {**base, 'status': 'unavailable', 'records': [],
                'error_code': code, 'upstream_status': upstream_status, 'message': message}
    if not commodity:
        return {**base, 'status': 'needs_commodity', 'records': [],
                'message': 'Enter the exact mandi commodity name; no processing-form conversion is assumed.'}
    if not district:
        return {**base, 'status': 'needs_district', 'records': [],
                'message': 'This government resource requires a district. Enter the district containing the market.'}
    key = (commodity, state, district, requested_date.isoformat())
    cached = CACHE.get(key)
    if cached and time.time() - cached[0] < 21600:
        return {**cached[1], 'status': 'cached', 'cache_age_seconds': round(time.time()-cached[0])}
    api_key = os.getenv('DATA_GOV_API_KEY', '').strip()
    if not api_key:
        return {**base, 'status': 'unavailable', 'records': [], 'message': 'Set DATA_GOV_API_KEY on the server to enable live prices. No reference price has been invented.'}
    params = {'api-key': api_key, 'format': 'json', 'limit': 100, 'offset': 0,
              'filters[Commodity]': commodity, 'filters[State]': state,
              'filters[District]': district,
              'filters[Arrival_Date]': requested_date.strftime('%d-%m-%Y')}
    try:
        # Keep connection failures quick, but allow slow government queries more
        # time to return. Avoid automatic retries that multiply provider load.
        async with httpx.AsyncClient(timeout=httpx.Timeout(READ_TIMEOUT_SECONDS, connect=10)) as client:
            response = await client.get(f'https://api.data.gov.in/resource/{RESOURCE}', params=params)
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ValueError('Unexpected provider response')
        if not isinstance(data.get('records'), list):
            raise ValueError('Unexpected provider response')
        records = []
        for original in data['records']:
            if not isinstance(original, dict):
                continue
            # This resource uses State/Modal_Price/etc.; the frontend contract
            # stays lowercase. Lowercase also accepts prior cached/test schemas.
            row = {k.lower(): v for k, v in original.items()}
            # Defensive exact filtering prevents displaying a different location's quote.
            if row.get('state', '').casefold() != state.casefold() or row.get('commodity', '').casefold() != commodity.casefold():
                continue
            if district and row.get('district', '').casefold() != district.casefold():
                continue
            try:
                reported = datetime.strptime(str(row.get('arrival_date')), '%d/%m/%Y').date()
            except ValueError:
                try:
                    reported = datetime.strptime(str(row.get('arrival_date')), '%d-%m-%Y').date()
                except ValueError:
                    continue
            if reported != requested_date:
                continue  # Never present an unfiltered historical record as today's quote.
            try:
                modal = float(row['modal_price'])
                if not math.isfinite(modal) or modal <= 0:
                    continue
            except (ValueError, TypeError, KeyError):
                continue
            records.append({k: row.get(k) for k in ('state','district','market','commodity','variety','grade','arrival_date','min_price','max_price','modal_price')})
        result = {**base, 'status': 'live' if records else 'no_data', 'records': records,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'message': f'Up to 100 matching quotes for {requested_date.isoformat()}. These are reported prices for the selected date, not harvest-price forecasts.' if records else 'No matching quotes returned for this crop, district and reporting date. Try a recent earlier date or verify the official commodity/district spelling.',
            'provider_total': data.get('total')}
        if records:
            CACHE[key] = (time.time(), result)
        return result
    except httpx.ConnectTimeout:
        return failure('connection_timeout', 'Could not establish a connection to data.gov.in within 10 seconds. Check network access and provider availability.')
    except httpx.TimeoutException:
        return failure('provider_timeout', f'data.gov.in did not respond within {READ_TIMEOUT_SECONDS} seconds while waiting for a response. The provider or network path may be slow; key validity remains unconfirmed.')
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        if status in (401, 403):
            return failure('access_denied', 'data.gov.in denied access. Verify your API key and resource access in your data.gov.in account; provider security restrictions can also cause this.', status)
        if status == 429:
            return failure('rate_limited', 'data.gov.in rate limit reached. Wait before retrying.', status)
        return failure('provider_http_error', f'data.gov.in returned HTTP {status}. Retry later or verify the resource is available.', status)
    except httpx.RequestError:
        return failure('connection_failed', 'Could not connect securely to data.gov.in. Check internet access, proxy/firewall settings and provider availability.')
    except (ValueError, TypeError):
        return failure('invalid_provider_response', 'data.gov.in returned an unexpected response instead of market records. Verify the resource/API access and retry later.')
