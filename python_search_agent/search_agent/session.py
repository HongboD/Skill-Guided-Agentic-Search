"""Execute search, open, and finish; save exact tool results and query rankings."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from .retrieval import QueryError, RetrievalFailure

def render_response(response):
    """Use this encoding for both the trajectory and model tool result."""
    return json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def _now():
    return datetime.now(timezone.utc).isoformat()

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
                raise RetrievalFailure('duplicate document in a stored query ranking')
            seen.add(doc_id)
            scores.setdefault(doc_id, []).append(1.0 / (k + rank))
    ordered = sorted(((doc_id, math.fsum(values)) for doc_id, values in scores.items()), key=lambda item: (-item[1], item[0]))[:depth]
    return [{'doc_id': doc_id, 'rank': rank, 'score': score} for rank, (doc_id, score) in enumerate(ordered, 1)]

class Session:
    """A fresh session; only successful finish changes its completion state."""

    def __init__(self, backend, run_dir, config):
        self.backend, self.run_dir, self.config = (backend, Path(run_dir), dict(config))
        self.page_size = config.get('page_size', 20)
        self.snippet_chars = config.get('snippet_chars', 600)
        self.open_chars = config.get('open_chars')
        self.ranking_depth = config.get('ranking_depth', 1000)
        self.max_final_queries = config.get('max_final_queries', 3)
        self.rrf_k = config.get('rrf_k', 60)
        if self.page_size != 20 or self.snippet_chars != 600 or self.max_final_queries != 3 or (not _integer(self.ranking_depth)) or (not _integer(self.rrf_k, 0)) or (self.open_chars is not None and (not _integer(self.open_chars))):
            raise ValueError('invalid frozen tool or ranking configuration')
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.run_dir / 'session_events.jsonl'
        if self.events_path.exists() or (self.run_dir / 'query_results').exists():
            raise ValueError('search session already exists')
        self.query_dir = self.run_dir / 'query_results'
        self.query_dir.mkdir()
        self._query_cache, self._visible_ids, self._call_ids = ({}, set(), set())
        self._steps = self.search_attempts = self.open_attempts = 0
        self.final_query_ids, self.finalized = ([], False)

    @property
    def query_cache(self):
        """Return a copy of the complete saved query records."""
        return deepcopy(self._query_cache)

    def _append(self, event):
        with self.events_path.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(render_response(event) + '\n')
            stream.flush()

    def _save(self, path, value):
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(render_response(value) + '\n')

    def dispatch(self, tool_name, arguments, call_id):
        """Execute one unique call and record its exact result or tool error."""
        if not isinstance(call_id, str) or not call_id:
            raise RetrievalFailure('missing tool call ID')
        if call_id in self._call_ids:
            raise RetrievalFailure('duplicate tool call ID')
        self._call_ids.add(call_id)
        self._steps += 1
        step = self._steps
        self._append({'event': 'tool_intent', 'step': step, 'call_id': call_id, 'tool': tool_name, 'arguments': arguments, 'time': _now()})
        if tool_name == 'search':
            self.search_attempts += 1
        elif tool_name == 'open':
            self.open_attempts += 1
        try:
            if self.finalized:
                raise QueryError('session_finished', 'The session is finished.')
            if not isinstance(arguments, dict):
                raise QueryError('invalid_arguments', 'Tool arguments must be an object.')
            if tool_name == 'search':
                response = self._search(arguments)
            elif tool_name == 'open':
                response = self._open(arguments)
            elif tool_name == 'finish':
                response = self._finish(arguments)
            else:
                raise QueryError('unknown_tool', 'Available tools: search, open, finish.')
        except QueryError as error:
            response = {'ok': False, 'error': {'code': error.code, 'message': str(error)}}
        except Exception as error:
            self._append({'event': 'infrastructure_error', 'step': step, 'call_id': call_id, 'tool': tool_name, 'error_type': type(error).__name__, 'message': str(error), 'time': _now()})
            if isinstance(error, RetrievalFailure):
                raise
            raise RetrievalFailure('search tool infrastructure failed: ' + str(error)) from error
        encoded = render_response(response)
        self._append({'event': 'tool_result', 'step': step, 'call_id': call_id, 'tool': tool_name, 'response': response, 'actual_returned_text': encoded, 'time': _now()})
        return response

    def _search(self, arguments):
        """Save the full ranking and expose one page with 600-character previews."""
        if set(arguments) - {'query', 'offset'} or not isinstance(arguments.get('query'), str) or (not arguments['query'].strip()) or (not _integer(arguments.get('offset', 0), 0)):
            raise QueryError('invalid_arguments', 'search requires query text and an optional non-negative integer offset.')
        query, offset = (arguments['query'], arguments.get('offset', 0))
        if offset % self.page_size:
            raise QueryError('invalid_offset', 'offset must be a multiple of 20.')
        query_id = f'q{self.search_attempts:06d}'
        data = self.backend.search(query, offset=offset, page_size=self.page_size, ranking_depth=self.ranking_depth)
        self._validate_backend_result(data, offset)
        hits = [{'doc_id': hit['doc_id'], 'rank': hit['rank'], 'score': hit['score'], 'title': hit['title'], 'snippet': hit['contents'][:self.snippet_chars]} for hit in data['hits']]
        record = {'query_id': query_id, 'query': query, 'offset': offset, 'parsed_query': data['parsed_query'], 'total_hits': data['total_hits'], 'ranking_depth': self.ranking_depth, 'ranking': data['ranking']}
        self._save(self.query_dir / (query_id + '.json'), record)
        self._query_cache[query_id] = record
        self._visible_ids.update((hit['doc_id'] for hit in hits))
        return {'ok': True, 'query_id': query_id, 'query': query, 'parsed_query': data['parsed_query'], 'total_hits': data['total_hits'], 'offset': offset, 'page_size': self.page_size, 'hits': hits, 'next_offset': offset + self.page_size if offset + len(hits) < data['total_hits'] else None}

    def _validate_backend_result(self, data, offset):
        if not isinstance(data, dict) or not _integer(data.get('total_hits'), 0) or (not isinstance(data.get('parsed_query'), str)) or (not isinstance(data.get('hits'), list)) or (not isinstance(data.get('ranking'), list)):
            raise RetrievalFailure('invalid backend result schema')
        if len(data['hits']) != min(self.page_size, max(0, data['total_hits'] - offset)):
            raise RetrievalFailure('backend returned an incomplete result page')
        if len(data['ranking']) != min(self.ranking_depth, data['total_hits']):
            raise RetrievalFailure('backend returned an incomplete deep ranking')
        for name in ('hits', 'ranking'):
            rows = data[name]
            if any((not isinstance(row, dict) or not isinstance(row.get('doc_id'), str) or (not row['doc_id']) or isinstance(row.get('score'), bool) or (not isinstance(row.get('score'), (int, float))) or (not math.isfinite(row['score'])) for row in rows)):
                raise RetrievalFailure('invalid backend document or score')
            if len({row['doc_id'] for row in rows}) != len(rows):
                raise RetrievalFailure('backend returned duplicate document IDs')
        for rank, hit in enumerate(data['hits'], offset + 1):
            if hit.get('rank') != rank or not isinstance(hit.get('title'), str) or (not isinstance(hit.get('contents'), str)):
                raise RetrievalFailure('invalid backend visible document')
            if rank <= len(data['ranking']) and hit['doc_id'] != data['ranking'][rank - 1]['doc_id']:
                raise RetrievalFailure('visible page and deep ranking disagree')

    def _open(self, arguments):
        """Return stored text only for an ID already displayed in this session."""
        if set(arguments) != {'doc_id'} or not isinstance(arguments['doc_id'], str):
            raise QueryError('invalid_arguments', 'open requires one document ID.')
        doc_id = arguments['doc_id']
        if doc_id not in self._visible_ids:
            raise QueryError('document_not_seen', 'Open an ID that appeared in a search result in this session.')
        document = self.backend.get(doc_id)
        if not isinstance(document, dict) or str(document.get('id')) != doc_id or (not isinstance(document.get('title'), str)) or (not isinstance(document.get('contents'), str)):
            raise RetrievalFailure('invalid stored document')
        contents = document['contents']
        visible = contents if self.open_chars is None else contents[:self.open_chars]
        metadata = document.get('metadata', {})
        if not isinstance(metadata, dict):
            raise RetrievalFailure('invalid stored document metadata')
        public = {key: metadata[key] for key in ('doc_id', 'pmid', 'offset', 'length', 'source_id') if key in metadata}
        return {'ok': True, 'doc_id': doc_id, 'title': document['title'], 'contents': visible, 'metadata': public, 'characters': len(contents), 'truncated': len(visible) < len(contents)}

    def _finish(self, arguments):
        """Validate one to three distinct queries and freeze their fused ranking."""
        ids = arguments.get('query_ids')
        if set(arguments) != {'query_ids'} or not isinstance(ids, list) or (not 1 <= len(ids) <= self.max_final_queries) or any((not isinstance(ident, str) for ident in ids)) or (len(set(ids)) != len(ids)):
            raise QueryError('invalid_arguments', 'finish requires one to three distinct executed query IDs.')
        if any((ident not in self._query_cache for ident in ids)):
            raise QueryError('unknown_query_id', 'Select query IDs from successful search calls in this session.')
        texts = [self._query_cache[ident]['query'].strip() for ident in ids]
        if len(set(texts)) != len(texts):
            raise QueryError('duplicate_query_text', 'Select different query texts; repeated searches and pages do not add fusion weight.')
        ranking = reciprocal_rank_fusion([self._query_cache[ident]['ranking'] for ident in ids], k=self.rrf_k, depth=self.ranking_depth)
        self._save(self.run_dir / 'final_selection.json', {'query_ids': list(ids), 'rrf_k': self.rrf_k, 'ranking_depth': self.ranking_depth, 'ranking': ranking})
        self.final_query_ids, self.finalized = (list(ids), True)
        return {'ok': True, 'finished': True, 'query_ids': list(ids), 'ranked_documents': len(ranking)}

    def selected_ranking(self):
        """Recreate the final ranking from the selected saved query lists."""
        if not self.finalized:
            raise ValueError('session has no final query selection')
        return reciprocal_rank_fusion([self._query_cache[ident]['ranking'] for ident in self.final_query_ids], k=self.rrf_k, depth=self.ranking_depth)

    def all_queries_ranking(self):
        """Controller-only sensitivity ranking; repeated query text counts once."""
        texts, rankings = (set(), [])
        for record in self._query_cache.values():
            text = record['query'].strip()
            if text not in texts:
                texts.add(text)
                rankings.append(record['ranking'])
        return reciprocal_rank_fusion(rankings, k=self.rrf_k, depth=self.ranking_depth)
