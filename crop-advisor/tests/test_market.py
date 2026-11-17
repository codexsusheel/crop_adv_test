"""Offline provider-contract tests, distinct from a live authenticated API test."""
import unittest
from unittest.mock import patch
import httpx
from backend import market

class MarketTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_filter_and_cache(self):
        market.CACHE.clear()
        row={'state':'Punjab','commodity':'Rice','modal_price':'2000','arrival_date':'16/11/2026','market':'Example','variety':'Example'}
        transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'records':[row,{**row,'state':'Other'}],'total':2}))
        original=httpx.AsyncClient
        with patch.dict('os.environ', {'DATA_GOV_API_KEY':'test-only'}), patch.object(market.httpx,'AsyncClient',side_effect=lambda **kwargs:original(transport=transport,**kwargs)):
            result=await market.prices('rice','Punjab')
            self.assertEqual(len(result['records']),1)
            self.assertEqual(result['status'],'live')
            self.assertEqual((await market.prices('rice','Punjab'))['status'],'cached')
        market.CACHE.clear()

    async def test_upstream_failure_is_safe(self):
        original=httpx.AsyncClient
        transport=httpx.MockTransport(lambda req:httpx.Response(403))
        with patch.dict('os.environ', {'DATA_GOV_API_KEY':'secret-test'}), patch.object(market.httpx,'AsyncClient',side_effect=lambda **kwargs:original(transport=transport,**kwargs)):
            result=await market.prices('rice','Punjab')
        self.assertEqual(result['status'],'unavailable')
        self.assertNotIn('secret-test',str(result))
