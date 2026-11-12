"""Execute explicit Lucene queries with fixed BM25 and analyzer settings."""
from __future__ import annotations
import json
import math
from pathlib import Path

class QueryError(ValueError):
    """The model query cannot be executed as written."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)

class RetrievalFailure(RuntimeError):
    """The retrieval environment failed; this is not a zero-result search."""
DEFAULT_ANALYZER = {'language': 'en', 'stemming': True, 'stemmer': 'porter', 'stopwords': True}

def query_fields(query):
    """Find explicit fields outside quotes; Lucene itself parses the syntax."""
    fields, token, quoted, regexp, escaped, separated = ([], [], False, False, False, False)
    for char in query:
        if escaped:
            if not quoted and (not regexp):
                token.append(char)
            escaped = False
        elif char == '\\':
            escaped = True
        elif char == '"' and (not regexp):
            quoted = not quoted
            token = []
        elif char == '/' and (not quoted):
            regexp = not regexp
            token = []
        elif quoted or regexp:
            continue
        elif char == ':':
            fields.append(''.join(token))
            token = []
        elif char.isspace():
            separated = True
        elif char in '()[]{}+-^~':
            token = []
        else:
            if separated:
                token = []
            token.append(char)
        if not char.isspace():
            separated = False
    return fields

def validate_query_fields(query, allowed_fields):
    """Reject empty queries and fields outside the fixed search interface."""
    if not isinstance(query, str) or not query.strip() or '\x00' in query:
        raise QueryError('invalid_query', 'query must be non-empty text without null characters')
    if set(query_fields(query)) - set(allowed_fields):
        raise QueryError('unknown_field', 'Allowed fields: ' + ', '.join(sorted(allowed_fields)))

def _positive_int(value, name, *, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, int) or value < (0 if allow_zero else 1):
        raise ValueError(name + ' must be a ' + ('non-negative' if allow_zero else 'positive') + ' integer')

def _is_query_exception(error):
    name = str(getattr(error, 'classname', '')) + ' ' + str(error)
    return any((part in name for part in ('ParseException', 'TokenMgrError', 'TooManyClauses', 'TooManyNestedClauses')))

class LuceneBackend:
    """Read a local raw-JSON index using explicit parsed queries and exact counts."""

    def __init__(self, index_path, config):
        self.index_path, self.config = (Path(index_path), dict(config))
        self.fields = tuple(config.get('fields', ('contents', 'title')))
        self.default_field = config.get('default_field', 'contents')
        if not self.fields or len(set(self.fields)) != len(self.fields) or any((field not in {'contents', 'title'} for field in self.fields)) or (self.default_field not in self.fields):
            raise ValueError('invalid searchable fields')
        self.analyzer_config = dict(config.get('analyzer', DEFAULT_ANALYZER))
        if set(self.analyzer_config) != set(DEFAULT_ANALYZER):
            raise ValueError('analyzer requires language, stemming, stemmer, stopwords')
        operator = config.get('default_operator', 'OR')
        if operator not in {'AND', 'OR'}:
            raise ValueError('default_operator must be AND or OR')
        bm25 = config.get('bm25')
        if not isinstance(bm25, dict) or set(bm25) != {'k1', 'b'}:
            raise ValueError('bm25 requires explicit k1 and b')
        if any((isinstance(x, bool) or not isinstance(x, (int, float)) or (not math.isfinite(x)) for x in bm25.values())) or bm25['k1'] <= 0 or (not 0 <= bm25['b'] <= 1):
            raise ValueError('invalid BM25 parameters')
        metadata_path = self.index_path / 'search_v2_index.json'
        if not metadata_path.is_file():
            raise RetrievalFailure('prepared Lucene index metadata is missing')
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        if metadata.get('status') != 'READY' or metadata.get('format') != 'search_v2_lucene_v1':
            raise RetrievalFailure('Lucene index build has not completed')
        if metadata.get('analyzer') != self.analyzer_config or set(metadata.get('fields', [])) != set(self.fields):
            raise RetrievalFailure('index and query analyzer/field configuration differ')
        if metadata.get('bm25') != bm25:
            raise RetrievalFailure('index and query BM25 configuration differ')
        try:
            from pyserini.analysis import get_lucene_analyzer
            from pyserini.pyclass import autoclass
            self.searcher = autoclass('io.anserini.search.SimpleSearcher')(str(self.index_path))
            self.analyzer = get_lucene_analyzer(**self.analyzer_config)
            self.searcher.set_analyzer(self.analyzer)
            self.searcher.set_bm25(float(bm25['k1']), float(bm25['b']))
            self.searcher.unset_rm3()
            parser_class = autoclass('org.apache.lucene.queryparser.classic.QueryParser')
            operator_class = autoclass('org.apache.lucene.queryparser.classic.QueryParser$Operator')
            self.parser = parser_class(self.default_field, self.analyzer)
            self.parser.setDefaultOperator(getattr(operator_class, operator))
            self.counter = autoclass('org.apache.lucene.search.IndexSearcher')(self.searcher.reader)
            self._filter = self.parser.parse(config['filter_query']) if config.get('filter_query') else None
            self._boolean_builder = autoclass('org.apache.lucene.search.BooleanQuery$Builder')
            self._occur = autoclass('org.apache.lucene.search.BooleanClause$Occur')
        except Exception as error:
            raise RetrievalFailure('Lucene initialization failed: ' + str(error)) from error

    def _parse(self, query):
        validate_query_fields(query, self.fields)
        try:
            parsed = self.parser.parse(query)
            if self._filter is not None:
                builder = self._boolean_builder()
                builder.add(parsed, self._occur.MUST)
                builder.add(self._filter, self._occur.FILTER)
                parsed = builder.build()
            return parsed
        except Exception as error:
            if _is_query_exception(error):
                raise QueryError('query_syntax', 'Lucene could not parse this query. Check operators, parentheses, phrases, and escapes.') from error
            raise RetrievalFailure('Lucene parsing failed: ' + str(error)) from error

    def search(self, query, offset=0, page_size=20, ranking_depth=1000):
        """Return one visible page and the complete ranking up to the task cutoff."""
        _positive_int(offset, 'offset', allow_zero=True)
        _positive_int(page_size, 'page_size')
        _positive_int(ranking_depth, 'ranking_depth')
        parsed = self._parse(query)
        try:
            total = int(self.counter.count(parsed))
            requested = min(total, max(offset + page_size, ranking_depth))
            hits = list(self.searcher.search(parsed, requested)) if requested else []
            rows = [{'doc_id': str(hit.docid), 'score': float(hit.score)} for hit in hits]
            if len({row['doc_id'] for row in rows}) != len(rows):
                raise RetrievalFailure('index returned duplicate document IDs')
            visible = []
            for rank, row in enumerate(rows[offset:offset + page_size], offset + 1):
                document = self.get(row['doc_id'])
                visible.append({**row, 'rank': rank, 'title': document['title'], 'contents': document['contents']})
            return {'total_hits': total, 'parsed_query': str(parsed.toString()), 'hits': visible, 'ranking': rows[:ranking_depth]}
        except (QueryError, RetrievalFailure):
            raise
        except Exception as error:
            if _is_query_exception(error):
                raise QueryError('query_syntax', 'Lucene cannot execute this query expression.') from error
            raise RetrievalFailure('Lucene search failed: ' + str(error)) from error

    def get(self, doc_id):
        """Read a stored document and its evaluation coordinates from the index."""
        try:
            document = self.searcher.doc(str(doc_id))
            if document is None:
                raise RetrievalFailure('a retrieved document is absent from the index')
            raw = document.get('raw')
            if not raw:
                raise RetrievalFailure('index does not contain raw document JSON')
            data = json.loads(raw)
            if not isinstance(data, dict) or str(data.get('id')) != str(doc_id) or (not isinstance(data.get('title'), str)) or (not isinstance(data.get('contents'), str)) or (not isinstance(data.get('metadata', {}), dict)):
                raise RetrievalFailure('stored document schema is invalid')
            return data
        except RetrievalFailure:
            raise
        except Exception as error:
            raise RetrievalFailure('Lucene document read failed: ' + str(error)) from error

    def close(self):
        """Release the controller's Java index reader."""
        if getattr(self, 'searcher', None) is not None:
            self.searcher.close()
            self.analyzer.close()
