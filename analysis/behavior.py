"""Measure actions using only neutral traces and earlier delivered evidence."""
from collections import Counter
import html,itertools,json,re,unicodedata
import numpy as np

def terms(text):
    text = unicodedata.normalize('NFKC', html.unescape(text)).casefold()
    return set(re.findall('[^\\W_]+', text)) - {'and', 'or', 'not', 'contents', 'title'}

def query_terms(text):
    text = re.sub('\\b(?:contents|title)\\s*:', '', text)
    text = re.sub('[~^]\\d+(?:\\.\\d+)?', '', text)
    return terms(text)

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def rows(p):
    with p.open(encoding='utf-8-sig') as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def blind_measure(folder, task):
    """No model, condition, score, source log, or provider fields enter here."""
    val = read(folder / 'validation.json')
    assert val['status'] == 'PASS'
    actions = {x['action_id']: x for x in rows(folder / 'actions.jsonl')}
    observations = {x['observation_id']: x for x in rows(folder / 'observations.jsonl')}
    batches = {x['batch_id']: i for i, x in enumerate(rows(folder / 'batches.jsonl'))}
    text = (folder / 'task.txt').read_text(encoding='utf-8')
    original = terms(text.split('\nRequest:\n', 1)[1].split('\nTools:\n', 1)[0])
    counts = Counter()
    sources = {}
    earlier = set()
    exposed = set()
    opened = set()
    queries = []
    selected = []
    successful = []
    for event in rows(folder / 'timeline.jsonl'):
        if event['event'] == 'tool_request':
            a = actions[event['action_id']]
            if a['executed']:
                counts[a['tool'] + '_attempts'] += 1
            else:
                counts['rejected_requests'] += 1
        if event['event'] != 'tool_result_received':
            continue
        a = actions[event['action_id']]
        if not a['executed']:
            continue
        response = observations[event['observation_id']]['response']
        tool = a['tool']
        batch = batches[a['batch_id']]
        if not response.get('ok'):
            counts[tool + '_errors'] += 1
            continue
        counts[tool + '_successes'] += 1
        visible = []
        if tool == 'search':
            query = a['arguments']['query']
            qt = query_terms(query)
            novel = qt - original - earlier
            adopted = sorted((t for t in novel if t in sources and sources[t] < batch))
            queries.append({'query': query, 'terms': qt, 'adopted': bool(adopted)})
            successful.append({'action_id': a['action_id'], 'query_id': response['query_id'], 'query': query, 'total_hits': response['total_hits'], 'offset': response['offset'], 'batch_id': a['batch_id'], 'adopted_terms': adopted, 'shown_ids': [h['doc_id'] for h in response['hits']]})
            earlier.update(qt)
            counts['paging_calls'] += int(response['offset'] > 0)
            counts['zero_hit_searches'] += int(response['total_hits'] == 0)
            counts['boolean_queries'] += int(bool(re.search('\\b(?:AND|OR|NOT)\\b', query)))
            counts['phrase_queries'] += int('"' in query)
            counts['proximity_queries'] += int(bool(re.search('"\\s*~\\d+', query)))
            for h in response['hits']:
                exposed.add(h['doc_id'])
                visible.append(h['title'] + '\n' + h['snippet'])
        elif tool == 'open':
            opened.add(response['doc_id'])
            visible.append(response['title'] + '\n' + response['contents'])
        elif tool == 'finish':
            selected = response['query_ids']
        for text in visible:
            for term in terms(text):
                sources.setdefault(term, batch)
    assert len(actions) == len(observations) == val['tool_requests']
    assert sum((v for k, v in counts.items() if k.endswith('_attempts'))) == val['executed_calls']
    assert selected
    sets = [q['terms'] for q in queries if q['terms']]
    distances = [1 - len(a & b) / len(a | b) for a, b in itertools.combinations(sets, 2)]
    parent = lambda x: x.split(':')[0] if task.startswith('genomics') else x
    searches = counts['search_successes']
    query_texts = {q['query'].strip() for q in queries}
    counts.update({k: 0 for k in ['search_attempts', 'search_errors', 'open_attempts', 'open_successes', 'open_errors']})
    metrics = dict(counts)
    metrics.update(searches=searches, unique_query_texts=len(query_texts), unique_documents_seen=len(exposed), unique_parent_documents_seen=len({parent(x) for x in exposed}), unique_documents_opened=len(opened), unique_parent_documents_opened=len({parent(x) for x in opened}), docs_per_search=len({parent(x) for x in opened}) / searches if searches else None, formulation_diversity=float(np.mean(distances)) if distances else None, lexical_evidence_adoption_rate=sum((q['adopted'] for q in queries[1:])) / (searches - 1) if searches > 1 else None, evidence_adoption_denominator=max(0, searches - 1), selected_query_count=len(selected), zero_hit_rate=counts['zero_hit_searches'] / searches if searches else None, paging_rate=counts['paging_calls'] / searches if searches else None, repeated_query_rate=1 - len(query_texts) / searches if searches else None, action_batches=len(batches), searches_per_action_batch=searches / len(batches) if batches else None)
    return (metrics, {'queries': successful, 'selected_query_ids': selected, 'opened_ids': sorted(opened)})
