"""Relative paths and JSON input/output for offline reproduction."""
import json
import os
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
ROOT=Path(os.environ.get('SEARCH_REPRO_DATA',PROJECT/'data/export')).resolve()
VENDOR=PROJECT/'retrieval_baselines/vendor'
OUTPUT=Path(os.environ.get('SEARCH_REPRO_OUTPUT',PROJECT/'runs/recomputed')).resolve()

def read(path):
    """Read UTF-8 JSON, allowing a byte-order mark."""
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path,value):
    """Write a reproducible result without modifying packaged reference data."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')

def save(name,value):
    """Save an analysis table in the recomputed-results directory."""
    write(OUTPUT/name,value)

def records(path):
    """Stream complete JSONL records."""
    with Path(path).open(encoding='utf-8-sig') as stream:
        for line in stream:
            if line.strip():yield json.loads(line)
