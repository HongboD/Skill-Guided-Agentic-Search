"""Run BM25 and Anserini RM3 from public topic text."""


def query_text(topic):
    """Join title, request, and protocol fields in their supplied order."""
    parts = [topic.get('text', '')]
    if topic.get('title') and topic['title'] not in parts[0]:
        parts.insert(0, topic['title'])
    parts.extend(topic.get('protocol', {}).values())
    return '\n\n'.join(parts)


def rank(backend, topic, method, depth, rm3):
    """Retrieve one list; apply the date filter to feedback and final results."""
    from pyserini.pyclass import autoclass
    if method not in {'bm25', 'rm3'}:
        raise ValueError('Choose bm25 or rm3.')
    text = query_text(topic)
    original = autoclass('io.anserini.search.query.BagOfWordsQueryGenerator')().buildQuery('contents', backend.analyzer, text)
    query = original
    if backend._filter is not None:
        builder = backend._boolean_builder()
        builder.add(original, backend._occur.MUST)
        builder.add(backend._filter, backend._occur.FILTER)
        query = builder.build()
    metadata = {'method': method, 'input_text': text, 'query': str(query.toString()),
                'feedback_terms': None}
    if method == 'bm25':
        hits = backend.searcher.search(query, depth)
        return [{'doc_id': str(hit.docid), 'rank': i, 'score': float(hit.score)}
                for i, hit in enumerate(hits, 1)], metadata
    searcher = backend.counter
    searcher.setSimilarity(backend.searcher.get_similarity())
    sort = autoclass('io.anserini.search.SearchCollection').BREAK_SCORE_TIES_BY_DOCID
    initial = searcher.search(query, rm3['fb_docs'], sort, True)
    scored = autoclass('io.anserini.search.ScoredDocs').fromTopDocs(initial, searcher)
    metadata['feedback_document_ids'] = [str(doc.get('id')) for doc in scored.lucene_documents]
    if not len(scored.lucene_docids):
        return [], metadata
    args = autoclass('io.anserini.search.SearchCollection$Args')()
    args.hits = depth
    tokens = autoclass('io.anserini.analysis.AnalyzerUtils').analyze(backend.analyzer, text)
    context = autoclass('io.anserini.rerank.RerankerContext')(
        searcher, None, original, None, text, tokens, backend._filter, args)
    reranker = autoclass('io.anserini.rerank.lib.Rm3Reranker')(
        backend.analyzer, None, 'contents', rm3['fb_terms'], rm3['fb_docs'],
        float(rm3['original_query_weight']), False, rm3['filter_terms'])
    output = reranker.rerank(scored, context)
    if context.feedbackTerms is None:
        raise ValueError('RM3 did not record its feedback terms.')
    metadata['feedback_terms'] = {str(row.getKey()): float(row.getValue())
                                  for row in context.feedbackTerms.entrySet()}
    return [{'doc_id': str(doc.get('id')), 'rank': i + 1, 'score': float(output.scores[i])}
            for i, doc in enumerate(output.lucene_documents)], metadata


def run_text(task, topic_id, ranking, method):
    """Serialize the computed order for the task's official evaluator."""
    import math
    lines, seen = [], set()
    for position, row in enumerate(ranking, 1):
        doc = row['doc_id']
        if (not isinstance(doc, str) or not doc or any(c.isspace() for c in doc)
                or doc in seen or row['rank'] != position or not math.isfinite(row['score'])):
            raise ValueError('Invalid ranking row.')
        seen.add(doc)
        score = len(ranking) - position + 1
        if task == 'genomics2007':
            pmid, start, size = doc.split(':')
            if not pmid.isdigit() or int(start) < 0 or int(size) <= 0:
                raise ValueError('Invalid passage coordinates.')
            lines.append(f'{topic_id} {pmid} {position} {score} {start} {size} {method}')
        else:
            second = '0' if task == 'tar2018_full' else 'Q0'
            lines.append(f'{topic_id} {second} {doc} {position} {score} {method}')
    return ''.join(line + '\n' for line in lines)
