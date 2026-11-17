"""Persist import outcomes even when a later batch fails. No keys or local paths."""
from datetime import datetime, timezone
from uuid import uuid4
from .market_store import history_collection, normalise

class ImportRun:
    def __init__(self, method, resource_id, filename=None, history=None):
        self.history = history_collection() if history is None else history
        self.id = uuid4().hex
        self.record = {'run_id':self.id,'method':method,'resource_id':resource_id,
                       'filename':filename,'started_at':datetime.now(timezone.utc),
                       'status':'running','accepted':0,'invalid':0,'batches':0}
        self.states=set();self.districts=set();self.commodities=set();self.dates=[]

    def __enter__(self):
        self.history.insert_one({'_id':self.id,**self.record})
        return self

    def batch(self, rows, counts):
        self.record['accepted']+=counts['accepted']
        self.record['invalid']+=counts['invalid']
        self.record['batches']+=1
        for row in rows:
            try:
                doc=normalise(row,self.record['resource_id'])
            except (ValueError,AttributeError):
                continue
            self.states.add(doc['state']);self.districts.add((doc['state'],doc['district']))
            self.commodities.add(doc['commodity'])
            self.dates=sorted(self.dates+[doc['report_date']])
            self.dates=[self.dates[0],self.dates[-1]]  # Keep only the span, not millions of dates.
        self.history.update_one({'_id':self.id},{'$set':self.snapshot()})

    def snapshot(self):
        return {**self.record,'coverage':{'states':sorted(self.states),
                'district_count':len(self.districts),'commodity_count':len(self.commodities),
                'date_from':self.dates[0] if self.dates else None,
                'date_to':self.dates[-1] if self.dates else None}}

    def __exit__(self, kind, error, traceback):
        self.record['status']='failed' if kind else 'completed_with_rejections' if self.record['invalid'] else 'completed'
        self.record['finished_at']=datetime.now(timezone.utc)
        if kind:
            self.record['error_type']=kind.__name__  # No raw exception (URI/key may appear).
        self.history.update_one({'_id':self.id},{'$set':self.snapshot()})
        return False
