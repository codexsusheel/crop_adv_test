"""Offline provider-contract tests, distinct from a live authenticated API test."""
import unittest
from unittest.mock import patch
import httpx
from datetime import date
from backend import market

class MarketTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_filter_and_cache(self):
        market.CACHE.clear()
        row={'State':'Punjab','District':'Amritsar','Commodity':'Rice','Modal_Price':'2000','Arrival_Date':'16/11/2026','Market':'Example','Variety':'Example'}
        def respond(req):
            self.assertEqual(req.url.params['filters[State]'], 'Punjab')
            self.assertEqual(req.url.params['filters[District]'], 'Amritsar')
            self.assertEqual(req.url.params['filters[Arrival_Date]'], '16-11-2026')
            return httpx.Response(200,json={'records':[row,{**row,'State':'Other'},{**row,'Arrival_Date':'16/11/2009'}],'total':3})
        transport=httpx.MockTransport(respond)
        original=httpx.AsyncClient
        with patch.dict('os.environ', {'DATA_GOV_API_KEY':'test-only'}), patch.object(market.httpx,'AsyncClient',side_effect=lambda **kwargs:original(transport=transport,**kwargs)):
            result=await market.prices('rice','Punjab',district='Amritsar',arrival_date=date(2026,11,16))
            self.assertEqual(len(result['records']),1)
            self.assertEqual(result['status'],'live')
            self.assertEqual(result['records'][0]['market'], 'Example')
            self.assertEqual((await market.prices('rice','Punjab',district='Amritsar',arrival_date=date(2026,11,16)))['status'],'cached')
        market.CACHE.clear()

    async def test_upstream_failure_is_safe(self):
        original=httpx.AsyncClient
        transport=httpx.MockTransport(lambda req:httpx.Response(403))
        with patch.dict('os.environ', {'DATA_GOV_API_KEY':'secret-test'}), patch.object(market.httpx,'AsyncClient',side_effect=lambda **kwargs:original(transport=transport,**kwargs)):
            result=await market.prices('rice','Punjab',district='Amritsar')
        self.assertEqual(result['status'],'unavailable')
        self.assertNotIn('secret-test',str(result))
        self.assertEqual(result['error_code'], 'access_denied')
        self.assertEqual(result['upstream_status'], 403)

    async def test_timeout_and_invalid_response(self):
        original = httpx.AsyncClient
        def timeout(request):
            raise httpx.ReadTimeout('secret-test', request=request)
        for handler, code in [(timeout, 'provider_timeout'),
                              (lambda req: httpx.Response(200, json=[]), 'invalid_provider_response'),
                              (lambda req: httpx.Response(429), 'rate_limited')]:
            transport = httpx.MockTransport(handler)
            with patch.dict('os.environ', {'DATA_GOV_API_KEY':'secret-test'}), patch.object(market.httpx,'AsyncClient',side_effect=lambda **kwargs:original(transport=transport,**kwargs)):
                result = await market.prices('apple', 'Telangana', district='Hyderabad')
            self.assertEqual(result['error_code'], code)
            self.assertNotIn('secret-test', str(result))
