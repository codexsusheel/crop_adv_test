"""Run with: python -m unittest discover -s tests -v"""
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
SOIL = dict(N=90, P=42, K=43, temperature=20.9, humidity=82, ph=6.5, rainfall=203)

class ApiTests(unittest.TestCase):
    def test_typical_input_and_repeatability(self):
        a = client.post('/predict', json=SOIL)
        self.assertEqual(a.status_code, 200)
        self.assertEqual(a.json()['recommendation'], 'rice')
        self.assertEqual(a.json(), client.post('/predict', json=SOIL).json())

    def test_abstention(self):
        result = client.post('/predict', json={**SOIL, 'rainfall':350}).json()
        self.assertEqual(result['status'], 'OUT_OF_RANGE')
        self.assertIsNone(result['recommendation'])
        self.assertIsNone(result['top_candidates'])

    def test_unusual_combination(self):
        raw = dict(zip(SOIL, [130,5,5,40,15,9.8,280]))
        self.assertEqual(client.post('/predict', json=raw).json()['status'], 'OUT_OF_RANGE')

    def test_invalid_and_missing_inputs(self):
        for raw in ({**SOIL,'ph':15}, {**SOIL,'N':'abc'}, {k:v for k,v in SOIL.items() if k!='humidity'}, {**SOIL,'state':'Punjab'}):
            self.assertEqual(client.post('/predict', json=raw).status_code, 422)

    def test_reports_and_pages(self):
        for path in ('/','/style.css','/app.js','/meta','/crops','/states','/metrics','/metrics/classwise','/metrics/confusion-matrix','/metrics/robustness','/metrics/decision-rules','/plots/classwise.png'):
            self.assertEqual(client.get(path).status_code, 200, path)
        matrix = client.get('/metrics/confusion-matrix').json()
        self.assertEqual(sum(map(sum,matrix['matrix'])),440)
        self.assertEqual(len(matrix['labels']),22)
        self.assertEqual(client.get('/crops/wheat').status_code,404)

    def test_land_and_what_if(self):
        self.assertEqual(client.post('/land-check',json={'crop':'rice','inputs':SOIL}).status_code,200)
        r=client.post('/what-if',json={'inputs':SOIL,'feature':'rainfall','value':350}).json()
        self.assertEqual(r['after']['status'],'OUT_OF_RANGE')
        self.assertAlmostEqual(sum(r['probability_changes'].values()),0)
        r=client.post('/what-if/sweep',json={'inputs':SOIL,'feature':'rainfall','start':200,'end':350,'steps':3})
        self.assertEqual(len(r.json()['points']),3)
        self.assertEqual(client.post('/what-if',json={'inputs':SOIL,'feature':'ph','value':15}).status_code,422)

    def test_profit_units(self):
        r=client.post('/profit',json=dict(area_ha=2,price_per_quintal=2000,low_yield_q_ha=20,typical_yield_q_ha=30,high_yield_q_ha=40,cost_per_ha=30000,duration_days=120)).json()
        self.assertEqual(r['scenarios']['typical']['profit_inr'],60000)
        self.assertEqual(r['break_even_yield_q_ha'],15)

    def test_fertilizer_responds_to_soil_levels(self):
        low = client.post('/fertilizer',json={'crop':'rice','inputs':{**SOIL,'N':0,'P':0,'K':0}}).json()
        high = client.post('/fertilizer',json={'crop':'rice','inputs':{**SOIL,'N':600,'P':100,'K':400}}).json()
        self.assertTrue(all(n['suggested_product'] for n in low['nutrients']))
        self.assertTrue(all(n['suggested_product'] is None for n in high['nutrients']))
        self.assertNotIn('products_kg',low)
        self.assertIsNone(low['source_url'])
        self.assertEqual(client.post('/fertilizer',json={'crop':'wheat','inputs':SOIL}).status_code,404)

    def test_confirmed_soil_units_and_boundaries(self):
        r=client.post('/fertilizer',json={'crop':'rice','inputs':{**SOIL,'N':240,'P':11,'K':110,'ph':5},'measurement_basis':'confirmed_available_kg_ha'}).json()
        self.assertTrue(all(n['status']=='medium' for n in r['nutrients']))
        self.assertTrue(r['warnings'])
        self.assertTrue(r['source_url'])
        self.assertEqual(client.post('/fertilizer',json={'crop':'rice','inputs':SOIL,'measurement_basis':'ppm'}).status_code,422)

    def test_forest_support_is_separate_from_calibration(self):
        from backend.main import model, FEATURES
        import pandas as pd
        import numpy as np
        raw=np.mean([c.estimator.predict_proba(pd.DataFrame([SOIL],columns=FEATURES))[0] for c in model.calibrated_classifiers_],axis=0)
        result=client.post('/predict',json=SOIL).json()
        for candidate in result['forest_candidates']:
            index=list(model.classes_).index(candidate['crop'])
            self.assertAlmostEqual(candidate['score'],raw[index])
        self.assertGreater(len([c for c in result['forest_candidates'] if c['score']>0]),1)
        self.assertIsNone(client.post('/predict',json={**SOIL,'rainfall':350}).json()['forest_candidates'])

    def test_market_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            r=client.get('/market/rice?state=Punjab').json()
        self.assertEqual(r['status'],'unavailable')
        self.assertEqual(r['records'],[])

    def test_rotation(self):
        r=client.post('/rotation',json={'previous_crop':'rice'}).json()
        self.assertIn('chickpea',r['candidates'])
        self.assertEqual(client.post('/rotation',json={'previous_crop':'apple'}).json()['candidates'],[])

if __name__ == '__main__':
    unittest.main()
