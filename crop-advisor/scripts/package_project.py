"""Create a clean ZIP, excluding caches, secrets and virtual environments."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json

root = Path(__file__).resolve().parents[1]
excluded = {'__pycache__', '.venv', '.git', '.ipynb_checkpoints'}
files = [p for p in root.rglob('*') if p.is_file() and not any(x in excluded for x in p.relative_to(root).parts)
         and p.name != '.env' and p.suffix not in ('.pyc', '.zip')]
manifest = {str(p.relative_to(root)).replace('\\','/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.name != 'manifest.json'}
(root / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
archive = root.parent / 'Crop-Advisor.zip'
with ZipFile(archive, 'w', ZIP_DEFLATED) as output:
    for p in files:
        if p.name != 'manifest.json':
            output.write(p, str(Path(root.name) / p.relative_to(root)))
    output.write(root / 'manifest.json', root.name + '/manifest.json')
with ZipFile(archive) as check:
    assert check.testzip() is None
print(f'Created {archive} ({archive.stat().st_size:,} bytes)')
