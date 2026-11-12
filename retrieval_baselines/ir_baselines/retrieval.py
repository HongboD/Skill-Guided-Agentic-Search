"""Open a local Lucene index with fixed lexical retrieval settings."""
import json
from pathlib import Path

DEFAULT_ANALYZER = {'language': 'en', 'stemming': True, 'stemmer': 'porter', 'stopwords': True}


class Index:
    """Read an index and retain the optional publication-date filter."""

    def __init__(self, path, config, publication_dates=None):
        from pyserini.analysis import get_lucene_analyzer
        from pyserini.pyclass import autoclass
        metadata = json.loads((Path(path) / 'search_v2_index.json').read_text(encoding='utf-8'))
        if metadata.get('status') != 'READY' or metadata.get('format') != 'search_v2_lucene_v1':
            raise ValueError('The index is not ready.')
        for field in ['analyzer', 'fields', 'bm25']:
            if metadata[field] != config[field]:
                raise ValueError('Index settings differ: ' + field)
        self.searcher = autoclass('io.anserini.search.SimpleSearcher')(str(path))
        self.analyzer = get_lucene_analyzer(**config['analyzer'])
        self.searcher.set_analyzer(self.analyzer)
        self.searcher.set_bm25(float(config['bm25']['k1']), float(config['bm25']['b']))
        self.searcher.unset_rm3()
        self.counter = autoclass('org.apache.lucene.search.IndexSearcher')(self.searcher.reader)
        self._boolean_builder = autoclass('org.apache.lucene.search.BooleanQuery$Builder')
        self._occur = autoclass('org.apache.lucene.search.BooleanClause$Occur')
        self._filter = None
        if publication_dates:
            from datetime import datetime
            if len(publication_dates) != 2:
                raise ValueError('Two publication dates are required.')
            for value in publication_dates:
                if len(value) != 8 or not value.isdigit():
                    raise ValueError('Publication dates must use YYYYMMDD.')
                datetime.strptime(value, '%Y%m%d')
            start, end = publication_dates
            if start > end:
                raise ValueError('Publication dates are reversed.')
            parser = autoclass('org.apache.lucene.queryparser.classic.QueryParser')('contents', self.analyzer)
            self._filter = parser.parse(f'publication_date:[{start} TO {end}]')

    def close(self):
        """Release the Lucene reader and analyzer."""
        self.searcher.close()
        self.analyzer.close()
