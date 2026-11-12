"""Check session duration policy without a sandbox, provider, or real clock wait."""
import io
import itertools
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from search_agent import execution
from search_agent.policy import make_request


class DurationTests(unittest.TestCase):
    def run_session(self, model, **options):
        request = make_request('Synthetic duration test.', {'model': model})
        response = {
            'output': [{'type': 'message', 'role': 'assistant', 'content': []}],
            'usage': {'input_tokens': 1, 'output_tokens': 0, 'total_tokens': 1},
        }
        events = [
            {'event': 'sandbox_probe', 'forbidden_paths_visible': [],
             'credential_environment_present': False},
            {'event': 'model_response', 'response': response},
            {'event': 'agent_complete', 'status': 'PASS'},
        ]
        process = MagicMock()
        process.stdout = io.StringIO(''.join(json.dumps(e) + '\n' for e in events))
        process.stdin = io.StringIO()
        process.returncode = 0
        process.poll.return_value = 0
        gateway = MagicMock()
        gateway.__enter__.return_value = SimpleNamespace(
            url='http://fixture.invalid', provider_user='fixture', models={model})
        session = SimpleNamespace(
            finalized=True, backend=SimpleNamespace(index_path=Path('/fixture-index')))
        # One simulated day checks that elapsed duration does not stop a session.
        clock = SimpleNamespace(monotonic=MagicMock(
            side_effect=itertools.chain([0], itertools.repeat(86400))))
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / 'session_events.jsonl').write_text('', encoding='utf-8')
            (folder / 'requests.jsonl').write_text(
                json.dumps(request) + '\n', encoding='utf-8')
            (folder / 'transport_audit.json').write_text(
                json.dumps({'status': 'PASS'}), encoding='utf-8')
            with patch.object(execution, 'Gateway', return_value=gateway), \
                    patch.object(execution, 'sandbox_command', return_value=['fixture']), \
                    patch.object(execution.subprocess, 'Popen', return_value=process), \
                    patch.object(execution, 'time', clock):
                return execution.execute_loop(folder, request, session, None, **options)

    def test_all_models_complete_without_a_session_limit(self):
        for model in ['gpt-6.1-sol', 'claude-sonnet-5-5', 'deepseek-flash']:
            for options in [{}, {'maximum_seconds': None}]:
                with self.subTest(model=model, options=options):
                    result = self.run_session(model, **options)
                    self.assertEqual(result['status'], 'PASS')
                    self.assertTrue(result['trajectory_audit']['ok'])

    def test_explicit_fixture_limit_is_still_enforced(self):
        with self.assertRaisesRegex(RuntimeError, 'supervisor_session_time_limit'):
            self.run_session('fixture', maximum_seconds=60)


if __name__ == '__main__':
    unittest.main()
