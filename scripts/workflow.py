"""Shared inputs, exact prompt assembly, and scoring for independent sessions."""
from datetime import datetime
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
TASKS = ('tot2023', 'genomics2007', 'tar2018_full')
CONDITIONS = ('S0', 'S1', 'S2', 'S3', 'S4')
PROTOCOL_FIELDS = ('objective', 'type_of_study', 'participants', 'index_tests',
                   'target_conditions', 'reference_standards')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                    allow_nan=False) + '\n', encoding='utf-8')


def validate_topic(topic, task):
    if task not in TASKS:
        raise ValueError('Unknown task: ' + task)
    ident = topic.get('topic_id')
    if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', ident):
        raise ValueError('topic_id must be a safe, nonempty string')
    for name in ('title', 'text'):
        if not isinstance(topic.get(name), str):
            raise ValueError('Topic requires string title and text')
    if not topic['text'].strip():
        raise ValueError('Topic text is empty')
    if task == 'tar2018_full':
        protocol = topic.get('protocol', {})
        if set(protocol) != set(PROTOCOL_FIELDS):
            raise ValueError('TAR requires all six public protocol fields')
        if any(not isinstance(protocol[k], str) for k in PROTOCOL_FIELDS):
            raise ValueError('Protocol values must be strings')
        dates = topic.get('publication_date_range')
        if not isinstance(dates, list) or len(dates) != 2:
            raise ValueError('TAR requires two publication dates')
        for value in dates:
            if not isinstance(value, str) or not re.fullmatch(r'\d{8}', value):
                raise ValueError('Publication dates must use YYYYMMDD')
            datetime.strptime(value, '%Y%m%d')
        if dates[0] > dates[1]:
            raise ValueError('Publication date range is reversed')
    return topic


def load_topics(path, task):
    rows = read_json(path)
    if not isinstance(rows, list) or not rows:
        raise ValueError('Topics must be a nonempty JSON array')
    seen = set()
    for row in rows:
        validate_topic(row, task)
        if row['topic_id'] in seen:
            raise ValueError('Duplicate topic ID: ' + row['topic_id'])
        seen.add(row['topic_id'])
    return rows


def select_topic(path, task, topic_id):
    for row in load_topics(path, task):
        if row['topic_id'] == topic_id:
            return row
    raise ValueError('Topic is absent from the supplied topics: ' + topic_id)


def assemble_prompt(task, topic, condition):
    validate_topic(topic, task)
    if condition not in CONDITIONS:
        raise ValueError('Unknown condition: ' + condition)
    goal = read_json(ROOT / 'prompts/goals.json')[task]
    request = topic['text']
    if topic['title'] and topic['title'] not in request:
        request = topic['title'] + '\n\n' + request
    if task == 'tar2018_full':
        request += '\n\nReview protocol:\n'
        request += '\n'.join(k.replace('_', ' ') + ': ' + topic['protocol'][k] for k in PROTOCOL_FIELDS)
        start, end = topic['publication_date_range']
        request += ('\n\nThe collection is filtered to the supplied publication date range: '
                    + start + ' to ' + end + '.')
    strategy = ''
    if condition in ('S1', 'S2', 'S3'):
        skill = (ROOT / 'prompts' / (condition + '.txt')).read_text(encoding='utf-8').rstrip('\n')
        strategy = '\nApply the following search strategy throughout the task.\n\n' + skill
    elif condition == 'S4':
        strategy = '\n' + (ROOT / 'prompts/S4.txt').read_text(encoding='utf-8').rstrip('\n').format(goal=goal)
    template = (ROOT / 'prompts/common.txt').read_text(encoding='utf-8')
    return template.format(goal=goal, request=request,
                           depth=5000 if task == 'tar2018_full' else 1000,
                           strategy=strategy)


def score_ranking(task, topic_id, ranking_path, qrels, output):
    """Convert a new agent ranking, then invoke the unchanged official scorer."""
    if task not in TASKS or not re.fullmatch(r'[A-Za-z0-9_-]+', topic_id):
        raise ValueError('Invalid task or topic ID')
    if not Path(qrels).is_file():
        raise FileNotFoundError('Supply the released task judgments with --qrels')
    sys.path.insert(0, str(ROOT / 'retrieval_baselines'))
    from ir_baselines.baselines import run_text
    from ir_baselines.evaluation import evaluate
    ranking = read_json(ranking_path)
    depth = 5000 if task == 'tar2018_full' else 1000
    if not isinstance(ranking, list) or len(ranking) > depth:
        raise ValueError('Ranking exceeds the task cutoff or is not a list')
    text = run_text(task, topic_id, ranking, 'skill_guided_search')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    run = output / 'run.trec'
    run.write_text(text, encoding='utf-8', newline='\n')
    return evaluate(task, run, [{'topic_id': topic_id}], output / 'scores', qrels_path=qrels)
