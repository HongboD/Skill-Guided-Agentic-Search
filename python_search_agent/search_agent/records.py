"""Write controller records without modifying model-facing text."""
from datetime import datetime,timezone
import json
from pathlib import Path

def timestamp():
    """Return UTC time for controller records."""
    return datetime.now(timezone.utc).isoformat()

def read(path):
    """Read a JSON configuration or result."""
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def dump(path,value):
    """Save one complete controller record."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def append(path,value):
    """Append one complete event to a JSONL record."""
    with Path(path).open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n')
