"""Synthetic integration checks; no benchmark datasets or model calls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from workflow import assemble_prompt, load_topics, score_ranking, PROTOCOL_FIELDS
from import_topics import import_topics


class WorkflowTests(unittest.TestCase):
    def topic(self):
        return {'topic_id': 'synthetic', 'title': 'A synthetic request', 'text': 'Find an imaginary item.'}

    def test_condition_changes_only_strategy(self):
        topic = self.topic()
        base = assemble_prompt('tot2023', topic, 'S0').rstrip('\n')
        for condition in ['S1', 'S2', 'S3', 'S4']:
            text = assemble_prompt('tot2023', topic, condition)
            self.assertTrue(text.startswith(base + '\n'))
        self.assertNotIn('# Search Strategy', base)
        self.assertIn('Task objective:', assemble_prompt('tot2023', topic, 'S4'))

    def test_tar_dates_and_protocol_are_required_and_rendered(self):
        topic = self.topic()
        with self.assertRaises(ValueError):
            assemble_prompt('tar2018_full', topic, 'S0')
        topic.update(protocol={k: 'Synthetic ' + k for k in PROTOCOL_FIELDS},
                     publication_date_range=['20000101', '20011231'])
        text = assemble_prompt('tar2018_full', topic, 'S3')
        self.assertIn('index tests: Synthetic index_tests', text)
        self.assertIn('20000101 to 20011231.', text)
        self.assertIn('up to 5000 results', text)
        bad = copy.deepcopy(topic)
        bad['publication_date_range'] = ['20000230', '20011231']
        with self.assertRaises(ValueError):
            assemble_prompt('tar2018_full', bad, 'S0')

    def test_import_drops_answer_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'topics.jsonl'
            path.write_text(json.dumps({'id': 'x', 'title': 'Synthetic', 'text': 'A request',
                                        'wikipedia_id': 'secret-answer', 'expert_query': 'excluded'}) + '\n')
            rows = import_topics(path, 'tot2023', 'tot-jsonl')
            self.assertEqual(set(rows[0]), {'topic_id', 'title', 'text'})
            self.assertNotIn('secret-answer', assemble_prompt('tot2023', rows[0], 'S0'))

    def test_dry_run_has_no_side_effects(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            topics = root / 'topics.json'
            topics.write_text(json.dumps([self.topic()]))
            output = root / 'run'
            command = [sys.executable, '-B', str(ROOT / 'scripts/run_experiment.py'),
                       '--task', 'tot2023', '--topic', 'synthetic', '--condition', 'S2',
                       '--topics', str(topics), '--index', str(root / 'absent-index'),
                       '--deployment', str(root / 'absent-config'), '--java-home', str(root),
                       '--loop-venv', str(root), '--output', str(output), '--skip-evaluation', '--dry-run']
            report = json.loads(subprocess.check_output(command, text=True, encoding='utf-8'))
            self.assertEqual(report['condition'], 'S2')
            self.assertFalse(output.exists())

    def test_duplicate_topics_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'topics.json'
            path.write_text(json.dumps([self.topic(), self.topic()]))
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                load_topics(path, 'tot2023')

    def test_tar_official_evaluation_from_agent_ranking(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            ranking = root / 'ranking.json'
            ranking.write_text(json.dumps([{'doc_id': '123', 'rank': 1, 'score': 0.1}]))
            qrels = root / 'judgments.txt'
            qrels.write_text('SYNTHETIC 0 123 1\nSYNTHETIC 0 456 1\n')
            result = score_ranking('tar2018_full', 'SYNTHETIC', ranking, qrels, root / 'evaluation')
            self.assertEqual(result['topics'][0]['primary_score'], 0.5)
            self.assertTrue((root / 'evaluation/run.trec').is_file())


if __name__ == '__main__':
    unittest.main()
