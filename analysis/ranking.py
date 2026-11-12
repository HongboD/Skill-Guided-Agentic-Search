"""Deterministic rank fusion and official run-file serialization."""
import math

def _integer(value, minimum=1):
    return isinstance(value, int) and (not isinstance(value, bool)) and (value >= minimum)

def reciprocal_rank_fusion(rankings, *, k=60, depth=1000):
    """Fuse lists; lexical document ID resolves equal scores."""
    if not _integer(k, 0) or not _integer(depth):
        raise ValueError('invalid fusion parameters')
    scores = {}
    for ranking in rankings:
        seen = set()
        for rank, row in enumerate(ranking, 1):
            doc_id = row['doc_id']
            if doc_id in seen:
                raise ValueError('duplicate document in a stored query ranking')
            seen.add(doc_id)
            scores.setdefault(doc_id, []).append(1.0 / (k + rank))
    ordered = sorted(((doc_id, math.fsum(values)) for doc_id, values in scores.items()), key=lambda item: (-item[1], item[0]))[:depth]
    return [{'doc_id': doc_id, 'rank': rank, 'score': score} for rank, (doc_id, score) in enumerate(ordered, 1)]

def validate_ranking(ranking, depth):
    if not isinstance(ranking, list) or len(ranking) > depth:
        raise ValueError('invalid_ranking_depth')
    ids = set()
    for i, row in enumerate(ranking, 1):
        ident = row.get('doc_id')
        if not isinstance(ident, str) or not ident or any((c.isspace() for c in ident)) or (ident in ids) or (row.get('rank') != i) or isinstance(row.get('score'), bool) or (not isinstance(row.get('score'), (int, float))) or (not math.isfinite(row['score'])):
            raise ValueError('invalid_ranking_row')
        ids.add(ident)

def trec_text(task, topic, ranking):
    lines, passages = ([], [])
    for i, row in enumerate(ranking, 1):
        ident, score = (row['doc_id'], len(ranking) - i + 1)
        if task.startswith('genomics'):
            pmid, start, size = ident.split(':')
            start, size = (int(start), int(size))
            if not pmid.isdigit() or start < 0 or size <= 0:
                raise ValueError('invalid_genomics_passage_id')
            passages.append({'pmid': pmid, 'offset': start, 'length': size})
            lines.append(f'{topic} {pmid} {i} {score} {start} {size} search_v2')
        else:
            action = '0' if task.startswith('tar2018') else 'Q0'
            lines.append(f'{topic} {action} {ident} {i} {score} search_v2')
    return (''.join((line + '\n' for line in lines)), passages)
