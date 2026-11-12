"""Command-line entry points for preparation, indexing, retrieval, and scoring."""
import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ('tot2023', 'genomics2007', 'tar2018_full')


def read(path):
    """Read a local JSON input."""
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    """Write a JSON result with explicit numeric values."""
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def select_topics(task, path=None, ids=None):
    """Load public topics and optionally select an explicit subset."""
    if path is None:
        raise ValueError('Supply downloaded topics with --topics; see docs/DATA.md')
    rows = read(path)
    available = {str(row['topic_id']) for row in rows}
    if len(available) != len(rows):
        raise ValueError('Duplicate topic IDs.')
    if ids:
        wanted = set(ids)
        if wanted - available:
            raise ValueError('Unknown topic IDs: ' + ', '.join(sorted(wanted - available)))
        rows = [row for row in rows if str(row['topic_id']) in wanted]
    if not rows:
        raise ValueError('No topics selected.')
    return rows


def run(args, config):
    """Retrieve fresh lists from the index and save every query and ranking."""
    from .baselines import rank, run_text
    from .retrieval import Index
    rows = select_topics(args.task, args.topics, args.topic)
    if args.evaluate and (not args.qrels or not Path(args.qrels).is_file()):
        raise ValueError('--evaluate requires --qrels with the released judgments')
    methods = ['bm25', 'rm3'] if args.method == 'both' else [args.method]
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'settings.json', config)
    write(output / 'topics.json', rows)
    depth = config['tasks'][args.task]['depth']
    for method in methods:
        folder = output / method
        folder.mkdir()
        with (folder / 'run.trec').open('w', encoding='utf-8', newline='\n') as run_file:
            for topic in rows:
                topic_id = str(topic['topic_id'])
                if not topic_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in topic_id):
                    raise ValueError('Unsafe topic ID.')
                dates = topic.get('publication_date_range')
                if args.task == 'tar2018_full' and not dates:
                    raise ValueError('TAR topics require an inclusive publication-date range.')
                backend = Index(args.index, config['retrieval'], dates)
                try:
                    ranking, detail = rank(backend, topic, method, depth, config['rm3'])
                finally:
                    backend.close()
                cell = folder / topic_id
                cell.mkdir()
                write(cell / 'ranking.json', ranking)
                write(cell / 'query.json', detail)
                text = run_text(args.task, topic_id, ranking, method)
                (cell / 'run.trec').write_text(text, encoding='utf-8')
                run_file.write(text)
                run_file.flush()
                print(f'{method} {args.task} {topic_id}: {len(ranking)} records', flush=True)
        if args.evaluate:
            from .evaluation import evaluate
            evaluate(args.task, folder / 'run.trec', rows, folder / 'evaluation', qrels_path=args.qrels)
    report = {'status': 'COMPLETE', 'task': args.task, 'topics': len(rows), 'methods': methods,
              'rankings': len(rows) * len(methods), 'fresh_retrieval': True}
    write(output / 'completion.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', help='Java 21 installation directory')
    parser.add_argument('--config', default=str(ROOT / 'config.json'))
    sub = parser.add_subparsers(dest='command', required=True)
    extract = sub.add_parser('extract', help='Extract a local ZIP into a new directory')
    extract.add_argument('--source', required=True)
    extract.add_argument('--output', required=True)
    prep = sub.add_parser('prepare', help='Convert local source records to JSONL')
    prep.add_argument('--kind', required=True, choices=['tot-raw', 'tot-tsv', 'genomics-html', 'genomics-tsv', 'pubmed2018'])
    prep.add_argument('--source', required=True)
    prep.add_argument('--spans')
    prep.add_argument('--output', required=True)
    build = sub.add_parser('index', help='Build a new Lucene index')
    build.add_argument('--jsonl', required=True)
    build.add_argument('--output', required=True)
    build.add_argument('--expected-count', type=int)
    execute = sub.add_parser('run', help='Generate fresh BM25/RM3 rankings')
    execute.add_argument('--task', choices=TASKS, required=True)
    execute.add_argument('--index', required=True)
    execute.add_argument('--method', choices=['bm25', 'rm3', 'both'], default='both')
    execute.add_argument('--topics', required=True)
    execute.add_argument('--qrels', help='Released judgments; required with --evaluate')
    execute.add_argument('--topic', action='append')
    execute.add_argument('--output', required=True)
    execute.add_argument('--evaluate', action='store_true')
    scoring = sub.add_parser('evaluate', help='Score a baseline run file')
    scoring.add_argument('--task', choices=TASKS, required=True)
    scoring.add_argument('--run', required=True)
    scoring.add_argument('--topics', required=True)
    scoring.add_argument('--qrels', required=True)
    scoring.add_argument('--topic', action='append')
    scoring.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.java_home:
        os.environ['JAVA_HOME'] = str(Path(args.java_home).resolve())
    config = read(args.config)
    if args.command == 'extract':
        from .extract import extract_zip
        result = extract_zip(args.source, args.output)
    elif args.command == 'prepare':
        from .prepare import prepare
        result = prepare(args.kind, args.source, args.output, args.spans)
    elif args.command == 'index':
        from .indexing import build_index, jsonl_records
        result = build_index(jsonl_records(args.jsonl), args.output, config['retrieval'])
        if args.expected_count is not None and result['document_count'] != args.expected_count:
            # A structurally valid index with the wrong collection count is not
            # ready for this requested collection.
            result['status'] = 'COUNT_MISMATCH'
            write(Path(args.output) / 'search_v2_index.json', result)
            raise ValueError('The built record count differs from --expected-count.')
    elif args.command == 'run':
        result = run(args, config)
    else:
        from .evaluation import evaluate
        result = evaluate(args.task, args.run, select_topics(args.task, args.topics, args.topic), args.output, qrels_path=args.qrels)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
