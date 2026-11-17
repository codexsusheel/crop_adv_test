"""Read-only market browser, independent of the classifier's 22 crop labels."""
from datetime import date
from fastapi import APIRouter, HTTPException, Query
from pymongo.errors import PyMongoError
from starlette.concurrency import run_in_threadpool
from . import market_store as store

router=APIRouter(prefix='/market',tags=['Stored market data'])

async def read(function, *args, **kwargs):
    try:
        return await run_in_threadpool(function, *args, **kwargs)
    except PyMongoError:
        raise HTTPException(503,'MongoDB is unavailable or the query timed out. Check the database service.') from None

@router.get('/options')
async def options(state: str | None=Query(None,max_length=100), district: str | None=Query(None,max_length=100),
                  commodity: str | None=Query(None,max_length=150), selected_date: date | None=Query(None,alias='date'),
                  market: str | None=Query(None,max_length=150)):
    return await read(store.options,state,district,commodity,selected_date,market)

@router.get('/prices')
async def prices(state: str=Query(min_length=1,max_length=100), district: str=Query(min_length=1,max_length=100),
                 commodity: str=Query(min_length=1,max_length=150), selected_date: date | None=Query(None,alias='date'),
                 market: str | None=Query(None,max_length=150), variety: str | None=Query(None,max_length=150)):
    return await read(store.lookup,state,district,commodity,selected_date,market=market,variety=variety)

@router.get('/status')
async def status():
    return await read(store.status)

@router.get('/imports')
async def imports():
    def records():
        return list(store.history_collection().find({}, {'_id':0}).sort('started_at',-1).limit(10).max_time_ms(3000))
    return {'imports':await read(records)}
