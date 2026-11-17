"""MongoDB persistence for government market records; no API calls on reads."""
import hashlib
import atexit
import json
import math
import os
from statistics import median
from datetime import date, datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo
from pymongo import MongoClient, UpdateOne

RESOURCE = '35985678-0d79-46b4-9ed6-6f13308a1d24'
SOURCE = 'https://www.data.gov.in/resource/variety-wise-daily-market-prices-data-commodity'
SOURCES = {RESOURCE: SOURCE,
           '9ef84268-d588-465a-a308-a864a43d0070': 'https://www.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi'}
FIELDS = ('state', 'district', 'market', 'commodity', 'variety', 'grade')

def column_name(value):
    # Government CSV exports sometimes XML-encode spaces in column names.
    return str(value).strip().lower().replace('_x0020_', '_').replace(' ', '_')

@lru_cache(maxsize=1)
def client():
    # Reuse a connection pool. Never log the URI: Atlas URIs may contain passwords.
    return MongoClient(os.getenv('MONGODB_URI', 'mongodb://127.0.0.1:27017'),
                       serverSelectionTimeoutMS=3000, connectTimeoutMS=3000,
                       socketTimeoutMS=5000, appname='crop-advisor')

@atexit.register
def close_client():
    if client.cache_info().currsize:
        client().close()
        client.cache_clear()

def collection():
    return client()[os.getenv('MONGODB_DATABASE', 'crop_advisor')]['market_prices']

def ensure_indexes(coll):
    coll.create_index([('state_key', 1), ('district_key', 1), ('commodity_key', 1),
                       ('report_date', -1), ('market', 1)], name='market_lookup')
    coll.create_index([('report_date', -1)], name='reporting_date')

def normalise(row, resource_id=RESOURCE):
    """Validate a government CSV/JSON row and create a deterministic identity.

    Prices may change; identity excludes prices so reimporting updates a quote
    rather than creating a duplicate. No crop-model training data is modified.
    """
    if resource_id not in SOURCES:
        raise ValueError('Unsupported government resource')
    row = {column_name(k): v for k, v in row.items() if k is not None}
    doc = {f: str(row.get(f) or '').strip() for f in FIELDS}
    if any(not doc[f] for f in ('state', 'district', 'market', 'commodity')):
        raise ValueError('Missing location or commodity')
    raw_date = str(row.get('arrival_date') or '').strip()
    for fmt in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d'):
        try:
            report_date = datetime.strptime(raw_date, fmt).date()
            break
        except ValueError:
            continue
    else:
        raise ValueError('Invalid reporting date')
    doc['report_date'] = report_date.isoformat()  # ISO dates sort chronologically.
    doc['arrival_date'] = report_date.strftime('%d/%m/%Y')
    for name in ('min_price', 'max_price', 'modal_price'):
        try:
            value = float(str(row.get(name, '')).replace(',', ''))
        except (TypeError, ValueError):
            raise ValueError('Invalid price') from None
        if not math.isfinite(value) or value < 0 or (name=='modal_price' and value==0):
            raise ValueError('Invalid price')
        doc[name] = value
    if not doc['min_price'] <= doc['modal_price'] <= doc['max_price']:
        raise ValueError('Prices are not ordered minimum <= modal <= maximum')
    for f in ('state', 'district', 'commodity'):
        doc[f + '_key'] = doc[f].casefold()
    identity = [resource_id, doc['report_date']] + [doc[f].casefold() for f in FIELDS]
    doc['_id'] = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
    doc['source_url'] = SOURCES[resource_id]
    doc['resource_id'] = resource_id
    doc['imported_at'] = datetime.now(timezone.utc)
    return doc

def save_rows(coll, rows, resource_id=RESOURCE):
    """Upsert one bounded batch; return explicit counts, never silently drop rows."""
    documents = {}
    invalid = 0
    accepted = 0
    for row in rows:
        try:
            doc = normalise(row, resource_id)
            documents[doc['_id']] = doc
            accepted += 1
        except (ValueError, AttributeError):
            invalid += 1
    if documents:
        coll.bulk_write([UpdateOne({'_id': key}, {'$set': {k:v for k,v in doc.items() if k!='_id'}},
                                  upsert=True) for key,doc in documents.items()], ordered=False)
    return {'accepted': accepted, 'invalid': invalid, 'unique_in_batch': len(documents)}

def lookup(state, district, commodity, selected_date=None, coll=None, market=None, variety=None):
    coll = collection() if coll is None else coll
    query = {'state_key': state.strip().casefold(), 'district_key': district.strip().casefold(),
             'commodity_key': commodity.strip().casefold()}
    if market:
        query['market'] = market.strip()
    if variety:
        query['variety'] = variety.strip()
    latest = coll.find_one(query, {'report_date': 1, '_id': 0}, sort=[('report_date', -1)], max_time_ms=3000)
    available_date = latest['report_date'] if latest else None
    requested = selected_date.isoformat() if selected_date else available_date
    records = []
    if requested:
        query['report_date'] = requested
        projection = {f: 1 for f in FIELDS + ('arrival_date','min_price','max_price','modal_price','resource_id','source_url')}
        projection['_id'] = 0
        records = list(coll.find(query, projection).sort([('modal_price', 1), ('market', 1)]).limit(1000).max_time_ms(3000))
    total = coll.count_documents(query, maxTimeMS=3000) if requested else 0
    sources = sorted({r.get('resource_id', RESOURCE) for r in records})
    return {'status': 'stored' if records else 'no_data', 'records': records,
            'provider': 'mongodb', 'sources': [{'resource_id': r, 'source_url': SOURCES.get(r)} for r in sources],
            'source_url': SOURCES.get(sources[0]) if len(sources)==1 else None,
            'resource_id': sources[0] if len(sources)==1 else None,
            'state': state, 'district': district, 'commodity': commodity,
            'requested_date': selected_date.isoformat() if selected_date else None,
            'reporting_date': requested, 'latest_available_date': available_date,
            'total_matching': total, 'returned': len(records), 'truncated': total > len(records),
            'summary': {'lowest_min': min(r['min_price'] for r in records),
                        'highest_max': max(r['max_price'] for r in records),
                        'median_modal': median(r['modal_price'] for r in records),
                        'market_count': len({r['market'] for r in records})} if records else None,
            'unit': 'INR/quintal; verify commodity form and variety',
            'message': f'Stored government quotes dated {requested}. Comparison covers displayed records; varieties and grades may differ. These are reported prices, not a live feed.' if records else
                       f'No imported quotes match this selection. Latest stored date for this location/commodity: {available_date or "none"}. Import government records first or choose another date.'}

def options(state=None, district=None, commodity=None, selected_date=None, market=None, coll=None):
    """Each step is constrained by its parents, avoiding impossible dropdown pairs."""
    coll = collection() if coll is None else coll
    query = {}
    result = {'states': sorted(coll.distinct('state', {}, maxTimeMS=3000)),
              'districts': [], 'commodities': [], 'dates': [], 'markets': [], 'varieties': []}
    if not state:
        return result
    query['state_key'] = state.strip().casefold()
    result['districts'] = sorted(coll.distinct('district', query, maxTimeMS=3000))
    if not district:
        return result
    query['district_key'] = district.strip().casefold()
    result['commodities'] = sorted(coll.distinct('commodity', query, maxTimeMS=3000))
    if not commodity:
        return result
    query['commodity_key'] = commodity.strip().casefold()
    result['dates'] = sorted(coll.distinct('report_date', query, maxTimeMS=3000), reverse=True)
    if not result['dates']:
        return result
    query['report_date'] = selected_date.isoformat() if selected_date else result['dates'][0]
    result['markets'] = sorted(coll.distinct('market', query, maxTimeMS=3000))
    if market:
        query['market'] = market
    result['varieties'] = sorted(coll.distinct('variety', query, maxTimeMS=3000))
    return result

def history_collection():
    return client()[os.getenv('MONGODB_DATABASE', 'crop_advisor')]['market_imports']

def status(coll=None):
    coll = collection() if coll is None else coll
    latest = coll.find_one({}, {'report_date':1,'_id':0}, sort=[('report_date',-1)], max_time_ms=3000)
    last_import = coll.find_one({}, {'imported_at':1,'_id':0}, sort=[('imported_at',-1)], max_time_ms=3000)
    latest_date = latest['report_date'] if latest else None
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    age = (today-date.fromisoformat(latest_date)).days if latest_date else None
    return {'records': coll.estimated_document_count(maxTimeMS=3000),
            'latest_reporting_date': latest_date, 'report_age_days': age,
            'last_record_imported_at': last_import.get('imported_at') if last_import else None,
            'freshness': 'empty' if age is None else 'future_dated' if age<0 else 'today' if age==0 else 'older',
            'states':len(coll.distinct('state', {}, maxTimeMS=3000)),
            'commodities':len(coll.distinct('commodity', {}, maxTimeMS=3000))}
