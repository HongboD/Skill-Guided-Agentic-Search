"""Check public-file scope, common sensitive metadata, and result coverage."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {'.git', 'data', 'datasets', 'corpora', 'indexes', 'runs', 'raw', 'private',
           '__pycache__', '.pytest_cache', '.ruff_cache', 'build', 'dist'}
FORBIDDEN_NAMES = {'corpus.jsonl', 'corpus.tsv', 'ranking.json', 'queries.jsonl',
                   'run.trec', 'session_events.jsonl', 'requests.jsonl'}
PATTERNS = [re.compile(r'[A-Z]:[\\/]Users[\\/][^\s"\']+', re.I),
            re.compile(r'/mnt/[a-z]/(?:paper|Users)/', re.I),
            re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
            re.compile(r'\bsk-[A-Za-z0-9_-]{24,}\b')]


def public_files():
    for path in ROOT.rglob('*'):
        parts = path.relative_to(ROOT).parts
        if any(p in IGNORED or p.startswith('.venv') for p in parts):
            continue
        if path.is_file():
            yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forbid', action='append', default=[], help='Additional private identity to scan for; never stored')
    args = parser.parse_args()
    files = list(public_files())
    issues = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if path.name in FORBIDDEN_NAMES or 'qrels' in path.parts or 'topics' in path.parts:
            issues.append(rel + ': benchmark/raw data file')
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            issues.append(rel + ': unexpected binary or non-UTF-8 artifact')
            continue
        if any(pattern.search(text) for pattern in PATTERNS):
            issues.append(rel + ': sensitive path or credential pattern')
        if any(value.casefold() in text.casefold() for value in args.forbid):
            issues.append(rel + ': forbidden identity')
    # Catch files already tracked even if the working-tree traversal excludes them.
    git = subprocess.run(['git', '-c', 'safe.directory=' + ROOT.as_posix(),
                          '-c', 'core.excludesfile=', 'ls-files', '-z'],
                         cwd=ROOT, capture_output=True)
    if git.returncode == 0:
        for name in git.stdout.decode('utf-8').split('\0'):
            if name and any(p in IGNORED for p in Path(name).parts):
                issues.append(name + ': tracked local-only directory')
    metrics = json.loads((ROOT / 'results/metrics.json').read_text(encoding='utf-8'))
    keys = {(r['model'], r['task'], r['topic_id'], r['condition']) for r in metrics}
    if len(metrics) != 3240 or len(keys) != 3240:
        issues.append('Result cohort is incomplete or contains duplicate cells')
    study = json.loads((ROOT / 'configs/study.json').read_text())
    expected = {(m, task, t, c) for m in study['models'] for task, info in study['tasks'].items()
                for t in info['topic_ids'] for c in study['conditions']}
    if keys != expected:
        issues.append('Results differ from the configured study cells')
    checksums = ROOT / 'results/SHA256SUMS'
    if checksums.exists():
        for line in checksums.read_text().splitlines():
            digest, name = line.split('  ', 1)
            actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            if actual != digest:
                issues.append(name + ': checksum mismatch')
    report = {'status': 'FAIL' if issues else 'PASS', 'public_files_checked': len(files),
              'result_cells': len(keys), 'benchmark_data_bundled': False if not issues else 'check issues',
              'issues': issues}
    print(json.dumps(report, indent=2))
    if issues:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
