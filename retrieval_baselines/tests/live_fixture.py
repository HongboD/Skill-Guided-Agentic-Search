"""Build a tiny real Lucene index and check date-filtered BM25/RM3."""
import json
from pathlib import Path
import tempfile
from ir_baselines.baselines import rank
from ir_baselines.indexing import build_index
from ir_baselines.retrieval import Index


def main():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / 'config.json').read_text())
    samples = [('alpha beta', '20000101'), ('alpha modern', '20200101'),
               ('beta gamma', '20000101')] + [('other material', '20000101')] * 25
    records = [{'id': str(i), 'title': '', 'contents': text, 'metadata': {'publication_date': date}}
               for i, (text, date) in enumerate(samples)]
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'index'
        built = build_index(records, path, config['retrieval'])
        assert built['document_count'] == 28
        backend = Index(path, config['retrieval'], ['19000101', '20100101'])
        try:
            bm25, _ = rank(backend, {'text': 'alpha'}, 'bm25', 20, config['rm3'])
            rm3, detail = rank(backend, {'text': 'alpha'}, 'rm3', 20, config['rm3'])
        finally:
            backend.close()
        assert [row['doc_id'] for row in bm25] == ['0']
        assert '1' not in [row['doc_id'] for row in rm3]
        assert detail['feedback_document_ids'] == ['0']
        assert detail['feedback_terms']
        print(json.dumps({'status': 'PASS', 'index_records': 28,
                          'bm25_date_filter': True, 'rm3_feedback_date_filter': True,
                          'rm3_final_date_filter': True, 'feedback_terms_recorded': True}))


if __name__ == '__main__':
    main()
