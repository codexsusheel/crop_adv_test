"""Storage parsing and Mongo-backed policy tests. No synthetic production data."""
from datetime import date
import unittest
from unittest.mock import patch
from backend.market_store import normalise, lookup, options, status
from backend import market_routes
from fastapi import HTTPException
from pymongo.errors import ServerSelectionTimeoutError
import os
from uuid import uuid4
from backend.market_store import client, ensure_indexes, save_rows

ROW={'State':'Telangana','District':'Hyderabad','Market':'Example test market',
     'Commodity':'Apple','Variety':'Test variety','Grade':'FAQ','Arrival_Date':'16/11/2026',
     'Min_Price':'1,000','Modal_Price':'1200','Max_Price':'1500'}

class StoreTests(unittest.TestCase):
    def test_government_encoded_csv_headers_and_source(self):
        row={k.replace('_Price','_x0020_Price'): v for k,v in ROW.items()}
        original='9ef84268-d588-465a-a308-a864a43d0070'
        result=normalise(row, original)
        self.assertEqual(result['modal_price'],1200)
        self.assertEqual(result['resource_id'],original)
        self.assertIn('current-daily-price',result['source_url'])
        self.assertNotEqual(result['_id'],normalise(ROW)['_id'])
    def test_identity_and_price_corrections(self):
        a=normalise(ROW);b=normalise({**ROW,'Modal_Price':'1300'})
        self.assertEqual(a['_id'],b['_id'])
        self.assertEqual(a['min_price'],1000)
        self.assertEqual(a['report_date'],'2026-11-16')
        self.assertNotEqual(a['_id'],normalise({**ROW,'Variety':'Another'})['_id'])
        for bad in ({'Modal_Price':'NaN'},{'Modal_Price':'900'},{'Arrival_Date':'bad'}):
            with self.assertRaises(ValueError):normalise({**ROW,**bad})

    @unittest.skipUnless(os.getenv('RUN_MONGO_INTEGRATION')=='1','Opt-in local Mongo integration test')
    def test_real_database_upserts_and_dates(self):
        # Only this uniquely named disposable test collection is removed.
        coll=client()['crop_advisor_tests']['test_'+uuid4().hex]
        try:
            ensure_indexes(coll)
            save_rows(coll,[ROW,ROW])
            self.assertEqual(coll.count_documents({}),1)
            save_rows(coll,[{**ROW,'Modal_Price':'1300'}, {**ROW,'Arrival_Date':'17/11/2026'}])
            self.assertEqual(coll.count_documents({}),2)
            old=lookup('telangana','hyderabad','apple',date(2026,11,16),coll)
            self.assertEqual(old['records'][0]['modal_price'],1300)
            latest=lookup('Telangana','Hyderabad','Apple',coll=coll)
            self.assertEqual(latest['reporting_date'],'2026-11-17')
            absent=lookup('Telangana','Hyderabad','Apple',date(2026,11,18),coll)
            self.assertEqual(absent['status'],'no_data')
            self.assertEqual(absent['latest_available_date'],'2026-11-17')
            choices=options('Telangana','Hyderabad','Apple',coll=coll)
            self.assertEqual(choices['districts'],['Hyderabad'])
            self.assertEqual(choices['commodities'],['Apple'])
            self.assertEqual(choices['dates'],['2026-11-17','2026-11-16'])
            self.assertEqual(options('Telangana','Siddipet',coll=coll)['commodities'],[])
            filtered=lookup('Telangana','Hyderabad','Apple',coll=coll,market='Missing')
            self.assertEqual(filtered['records'],[])
            self.assertEqual(latest['summary']['median_modal'],1200)
            self.assertEqual(latest['total_matching'],1)
            self.assertFalse(latest['truncated'])
            self.assertEqual(status(coll)['latest_reporting_date'],'2026-11-17')
        finally:
            coll.drop()

    @unittest.skipUnless(os.getenv('RUN_MONGO_INTEGRATION')=='1','Opt-in local Mongo integration test')
    def test_import_history_completed_and_failed_runs(self):
        from backend.import_history import ImportRun
        coll=client()['crop_advisor_tests']['history_'+uuid4().hex]
        try:
            with ImportRun('file','35985678-0d79-46b4-9ed6-6f13308a1d24','test.csv',history=coll) as run:
                run.batch([ROW],{'accepted':1,'invalid':1})
            record=coll.find_one({'run_id':run.id})
            self.assertEqual(record['status'],'completed_with_rejections')
            self.assertEqual(record['coverage']['states'],['Telangana'])
            self.assertEqual(record['coverage']['date_from'],'2026-11-16')
            with self.assertRaises(ValueError):
                with ImportRun('file','35985678-0d79-46b4-9ed6-6f13308a1d24',history=coll) as failed:
                    raise ValueError('private-value-not-to-log')
            record=coll.find_one({'run_id':failed.id})
            self.assertEqual(record['status'],'failed')
            self.assertNotIn('private-value',str(record))
        finally:
            coll.drop()

class MongoPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_market_route_reads_database(self):
        expected={'status':'stored','records':[]}
        with patch.object(market_routes.store,'lookup',return_value=expected) as read:
            result=await market_routes.prices('Telangana','Hyderabad','Apple',None,None,None)
            self.assertEqual(result,expected)
            read.assert_called_once_with('Telangana','Hyderabad','Apple',None,market=None,variety=None)

    async def test_db_failure_returns_safe_service_error(self):
        with patch.object(market_routes.store,'lookup',side_effect=ServerSelectionTimeoutError('private')):
            with self.assertRaises(HTTPException) as error:
                await market_routes.prices('Telangana','Hyderabad','Apple',None,None,None)
            self.assertEqual(error.exception.status_code,503)
            self.assertNotIn('private',str(error.exception.detail))
