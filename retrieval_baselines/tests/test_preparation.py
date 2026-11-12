"""Check corpus transformations, omission logs, and run-file coordinates."""
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from ir_baselines.baselines import query_text, run_text
from ir_baselines.extract import extract_zip
from ir_baselines.prepare import genomics_records, tot_records
from ir_baselines.pubmed import iter_pubmed_records
from ir_baselines.pubmed_versions import scan_versions


class PreparationTests(unittest.TestCase):
    def test_first_duplicate_is_retained_and_every_omission_is_logged(self):
        rows = [{'doc_id': 'a', 'page_title': 'First\ttitle', 'text': 'First\nbody'},
                {'doc_id': 'a', 'page_title': 'Second title', 'text': 'Second body'},
                {'doc_id': 'a', 'page_title': 'Third title', 'text': 'Third body'}]
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'raw.jsonl'
            original = ''.join(json.dumps(row) + '\n' for row in rows).encode()
            source.write_bytes(original)
            log = io.StringIO()
            records = list(tot_records(source, log))
            self.assertEqual(records[0]['contents'], 'First title\nFirst body')
            self.assertEqual(len(records), 1)
            omitted = [json.loads(line) for line in log.getvalue().splitlines()]
            self.assertEqual([row['source_line'] for row in omitted], [2, 3])
            self.assertEqual([row['record'] for row in omitted], rows[1:])
            self.assertEqual(source.read_bytes(), original)

    def test_genomics_slices_bytes_before_decoding(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            chunk = b'<p>caf\xe9\tcell</p><script>hidden</script>'
            (root / '123.html').write_bytes(b'header' + chunk + b'trailer')
            spans = root / 'spans.txt'
            spans.write_text(f'123 6 {len(chunk)}\n', encoding='ascii')
            row = next(genomics_records(root, spans))
            self.assertEqual(row['contents'], 'caf\u00e9 cell')
            self.assertEqual(row['id'], f'123:6:{len(chunk)}')
            self.assertEqual(row['metadata']['offset'], 6)

    def test_latest_pubmed_version_and_earliest_publication_date(self):
        def xml(version, title):
            return f'''<PubmedArticleSet><PubmedArticle><MedlineCitation>
<PMID Version="{version}">123</PMID><Article><ArticleTitle>{title}</ArticleTitle>
<Abstract><AbstractText Label="Aim">Body</AbstractText></Abstract>
<Journal><JournalIssue><PubDate><Year>2000</Year></PubDate></JournalIssue></Journal>
<ArticleDate><Year>2001</Year><Month>02</Month><Day>03</Day></ArticleDate>
</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>'''.encode()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = [root / 'part1.xml.gz', root / 'part2.xml.gz']
            for path, version in zip(paths, [1, 2]):
                with gzip.open(path, 'wb') as stream:
                    stream.write(xml(version, 'Old' if version == 1 else 'New'))
            selection = scan_versions(paths, root / 'selection.json')
            log = io.StringIO()
            with patch('ir_baselines.pubmed.pubmed_files', return_value=paths):
                rows = list(iter_pubmed_records(root, selection=selection, omitted_log=log))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['title'], 'New')
            self.assertEqual(rows[0]['metadata']['publication_date'], '20000101')
            self.assertEqual(json.loads(log.getvalue())['omitted_version'], 1)

    def test_zip_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'unsafe.zip'
            with zipfile.ZipFile(source, 'w') as archive:
                archive.writestr('../outside.txt', 'bad')
            with self.assertRaises(ValueError):
                extract_zip(source, root / 'output')
            self.assertFalse((root / 'outside.txt').exists())
            self.assertFalse((root / 'output').exists())

    def test_public_query_order_and_passage_run_format(self):
        topic = {'title': 'Title', 'text': 'Question', 'protocol': {'objective': 'Aim', 'participants': 'People'}}
        self.assertEqual(query_text(topic), 'Title\n\nQuestion\n\nAim\n\nPeople')
        ranking = [{'doc_id': '123:9:12', 'rank': 1, 'score': 0.75}]
        self.assertEqual(run_text('genomics2007', '200', ranking, 'bm25'), '200 123 1 1 9 12 bm25\n')


if __name__ == '__main__':
    unittest.main()
