"""Stream a downloaded government CSV/JSON into MongoDB in small upsert batches.

Usage: python scripts/import_market_data.py path/to/government.csv
No API key needed. Reimporting is safe; existing matching quotes are updated.
"""
import argparse
import csv
import json
import sys
from itertools import islice
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pymongo.errors import PyMongoError
from backend.market_store import collection, ensure_indexes, save_rows, column_name, SOURCES, RESOURCE
from backend.import_history import ImportRun

def read_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        if path.suffix.lower()=='.csv':
            reader = csv.DictReader(stream)
            columns = {column_name(c) for c in reader.fieldnames or []}
            if not {'state','district','market','commodity','arrival_date','min_price','max_price','modal_price'} <= columns:
                raise ValueError('Not a supported government price CSV; required columns are missing.')
            yield from reader
        elif path.suffix.lower() in ('.jsonl', '.ndjson'):
            for line in stream:
                if line.strip():
                    yield json.loads(line)
        elif path.suffix.lower()=='.json':
            body=json.load(stream)
            rows=body.get('records') if isinstance(body,dict) else body
            if not isinstance(rows,list):
                raise ValueError('JSON must be a records array or government response with records.')
            yield from rows
        else:
            raise ValueError('Use .csv, .json, .jsonl or .ndjson')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file',type=Path)
    parser.add_argument('--resource-id', choices=list(SOURCES), help='Government resource ID; inferred when the filename is a known resource UUID')
    args=parser.parse_args()
    resource_id = args.resource_id or (args.file.stem if args.file.stem in SOURCES else RESOURCE)
    print('Source resource:', resource_id, flush=True)
    coll=collection()
    ensure_indexes(coll)
    counts={'accepted':0,'invalid':0,'unique_in_batch':0}
    rows=iter(read_rows(args.file))
    with ImportRun('file',resource_id,args.file.name) as run:
        while batch:=list(islice(rows,500)):
            result=save_rows(coll,batch,resource_id)
            run.batch(batch,result)
            for name in counts:
                counts[name]+=result[name]
            print(json.dumps(counts),flush=True)
    print('Finished. Repeated records were upserted, not duplicated.',flush=True)

if __name__=='__main__':
    try:
        main()
    except (PyMongoError,ValueError,OSError) as error:
        print(f'Import stopped ({type(error).__name__}). Check file format, MongoDB connection and permissions. Any completed batches remain saved.',file=sys.stderr)
        sys.exit(1)
