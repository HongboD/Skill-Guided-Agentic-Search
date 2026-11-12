"""Normalize downloaded topics without exposing answers or expert queries to the agent."""
import argparse
import json
from pathlib import Path
import re
from workflow import ROOT, TASKS, validate_topic, write_json


def import_topics(source, task, format_name):
    text = Path(source).read_text(encoding='utf-8-sig')
    if format_name == 'genomics-text':
        if task != 'genomics2007':
            raise ValueError('genomics-text is only valid for genomics2007')
        rows = []
        for line in text.splitlines():
            if not line.strip():
                continue
            match = re.fullmatch(r'<(\d+)>(.*)', line)
            if match is None:
                raise ValueError('Expected <topic_id>question in Genomics topics')
            rows.append({'topic_id': match[1], 'title': '', 'text': match[2]})
    else:
        raw = ([json.loads(line) for line in text.splitlines() if line.strip()]
               if format_name == 'tot-jsonl' else json.loads(text))
        if not isinstance(raw, list):
            raise ValueError('JSON topics must be an array')
        rows = []
        for item in raw:
            # Deliberate allowlist: qrels, answers and expert Boolean queries never enter a prompt.
            row = {'topic_id': str(item.get('topic_id', item.get('id', ''))),
                   'title': item.get('title', ''), 'text': item['text']}
            if task == 'tar2018_full':
                row['protocol'] = item['protocol']
                row['publication_date_range'] = item['publication_date_range']
            rows.append(row)
    seen = set()
    for row in rows:
        validate_topic(row, task)
        if row['topic_id'] in seen:
            raise ValueError('Duplicate topic ID: ' + row['topic_id'])
        seen.add(row['topic_id'])
    if not rows:
        raise ValueError('No topics found')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', choices=TASKS, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--format', choices=['json', 'tot-jsonl', 'genomics-text'], default='json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--study-subset', action='store_true', help='Require and retain the exact published topic set')
    args = parser.parse_args()
    rows = import_topics(args.input, args.task, args.format)
    if args.study_subset:
        wanted = set(json.loads((ROOT / 'configs/study.json').read_text())['tasks'][args.task]['topic_ids'])
        missing = wanted - {r['topic_id'] for r in rows}
        if missing:
            parser.error('Missing study topics: ' + ', '.join(sorted(missing)))
        rows = [r for r in rows if r['topic_id'] in wanted]
    if args.output.exists():
        parser.error('Output file must be new')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, rows)
    print(f'Wrote {len(rows)} topics to {args.output}')


if __name__ == '__main__':
    main()
