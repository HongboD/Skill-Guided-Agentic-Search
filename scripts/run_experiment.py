"""Run one task/topic/condition/model cell; scheduling is up to the operator."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from workflow import ROOT, TASKS, CONDITIONS, assemble_prompt, select_topic, score_ranking, read_json, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', choices=TASKS, required=True)
    parser.add_argument('--topic', required=True)
    parser.add_argument('--condition', choices=CONDITIONS, required=True)
    parser.add_argument('--topics', type=Path, required=True)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--deployment', type=Path, required=True)
    parser.add_argument('--java-home', type=Path, required=True)
    parser.add_argument('--loop-venv', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--qrels', type=Path, help='Released judgments for official evaluation')
    parser.add_argument('--skip-evaluation', action='store_true')
    parser.add_argument('--dry-run', action='store_true', help='Show the assembled prompt and settings without calling a model')
    args = parser.parse_args()
    if not args.skip_evaluation and not args.qrels:
        parser.error('--qrels is required unless --skip-evaluation is set')
    topic = select_topic(args.topics, args.task, args.topic)
    prompt = assemble_prompt(args.task, topic, args.condition)
    output = args.output.resolve()
    metadata = {'task': args.task, 'topic_id': args.topic, 'condition': args.condition,
                'publication_date_range': topic.get('publication_date_range'),
                'session_limit_seconds': None}
    if args.dry_run:
        print(json.dumps({**metadata, 'prompt': prompt}, ensure_ascii=False, indent=2))
        return
    if output.exists():
        parser.error('Output directory must be new')
    for path in (args.topics, args.deployment):
        if not path.is_file():
            parser.error('Missing input file: ' + str(path))
    for path in (args.index, args.java_home, args.loop_venv):
        if not path.is_dir():
            parser.error('Missing runtime directory: ' + str(path))
    if args.qrels and not args.qrels.is_file():
        parser.error('Judgments file is missing')
    deployment = read_json(args.deployment)
    if deployment.get('session_seconds') is not None:
        parser.error('The study setup requires no session time limit')
    metadata['model'] = deployment['model']
    with tempfile.TemporaryDirectory(prefix='search-prompt-') as temporary:
        path = Path(temporary) / 'prompt.txt'
        path.write_text(prompt, encoding='utf-8')
        command = [sys.executable, '-B', '-m', 'search_agent',
                   '--prompt-file', str(path), '--task', args.task, '--output', str(output)]
        for name in ('index', 'deployment', 'java_home', 'loop_venv'):
            command += ['--' + name.replace('_', '-'), str(getattr(args, name).resolve())]
        if args.task == 'tar2018_full':
            command += ['--publication-dates', *topic['publication_date_range']]
        subprocess.run(command, cwd=ROOT / 'python_search_agent', check=True)
    write_json(output / 'experiment.json', metadata)
    if read_json(output / 'result.json').get('status') != 'PASS':
        raise RuntimeError('Session did not pass controller checks; see result.json')
    if not args.skip_evaluation:
        report = score_ranking(args.task, args.topic, output / 'ranking.json', args.qrels, output / 'evaluation')
        print(json.dumps(report, indent=2))
    print('Completed:', output)


if __name__ == '__main__':
    main()
