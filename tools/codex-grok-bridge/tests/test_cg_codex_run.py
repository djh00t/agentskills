"""Offline scenarios; all event data and pricing values are synthetic."""
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cg_codex_run as run


def fixture(**changes):
    event = {'type': 'turn.completed', 'usage': {
        'input_tokens': 100, 'cached_input_tokens': 20,
        'cache_write_input_tokens': 0, 'output_tokens': 5},
        'model': 'synthetic-model', 'duration_ms': 1500}
    event.update(changes)
    return json.dumps(event) + '\n'


class RunTest(unittest.TestCase):
    def test_spec_once(self):
        with tempfile.TemporaryDirectory() as root:
            req = dict(req_id='REQ-CG-20000101-001', prompt_file='prompt.txt',
                       base='main', branch='feat/test', timeout_s=60)
            first = run.spec(req, root)
            original = first['path'].read_bytes()
            second = run.spec(dict(req, model='changed'), root)
            self.assertEqual(first['path'], second['path'])
            self.assertEqual(first['path'].read_bytes(), original)
            self.assertEqual(json.loads(original), dict(req, model='gpt-6-luna'))
            self.assertTrue(first['launch_allowed'])
            self.assertFalse(second['launch_allowed'])
            self.assertEqual(second['status'], 'already specced')
            self.assertEqual(first['path'].stat().st_mode & 0o777, 0o600)

    def test_concurrent_spec_allows_one_launch(self):
        with tempfile.TemporaryDirectory() as root:
            req = dict(req_id='REQ-CG-20000101-001', prompt_file='prompt.txt',
                       base='main', branch='feat/test', timeout_s=60)
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: run.spec(req, root), range(8)))
            self.assertEqual(sum(r['launch_allowed'] for r in results), 1)
            self.assertEqual(len(list(Path(root).glob('*.json'))), 1)

    def test_spec_invalid_boundary(self):
        with tempfile.TemporaryDirectory() as root:
            req = dict(req_id='REQ-CG-20000101-001', prompt_file='prompt.txt',
                       base='main', branch='feat/test', timeout_s=60)
            for change in ({'req_id': '../escape'}, {'timeout_s': True},
                           {'timeout_s': float('nan')}, {'timeout_s': 0}, {'branch': ''}):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    run.spec(dict(req, **change), root)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_all_fields(self):
        result = run.usage(fixture())
        self.assertEqual({k: result[k] for k in ('model', 'input', 'cache_read',
                         'cache_write', 'output', 'wall_clock_s', 'completeness')},
                         dict(model='synthetic-model', input=100, cache_read=20,
                              cache_write=0, output=5, wall_clock_s=1.5, completeness='complete'))
        self.assertIsNone(result['est_cost_usd'])
        self.assertIsNone(result['billed_cost_usd'])

    def test_documented_exec_fields_missing_cache_write(self):
        # Exec JSON schema: turn.completed.usage; no model/time/cache-write guarantee.
        stream = fixture(model=None, duration_ms=None, usage={
            'input_tokens': 100, 'cached_input_tokens': 20, 'output_tokens': 5})
        result = run.usage(stream)
        self.assertEqual(result['input'], 100)
        for key in ('cache_write', 'model', 'wall_clock_s'):
            self.assertIsNone(result[key])
        self.assertEqual(result['completeness'], 'partial')

    def test_cancelled_retains_usage(self):
        for tail in ('{"type":"turn.started"}\n', '{"type":"error"}\n',
                     '{"type":"turn.failed"}\n', '{"type":'):
            with self.subTest(tail=tail):
                result = run.usage(fixture() + tail)
                self.assertEqual(result['output'], 5)
                self.assertEqual(result['input'], 100)
                self.assertEqual(result['completeness'], 'partial')
        result = run.usage(fixture(type='turn.failed'))
        self.assertEqual(result['input'], 100)
        self.assertEqual(result['completeness'], 'partial')

    def test_multiple_turns_and_unknowns(self):
        result = run.usage(fixture() + fixture())
        self.assertEqual((result['input'], result['output'], result['wall_clock_s']), (200, 10, 3))
        result = run.usage(fixture() + fixture(usage={'output_tokens': 3}))
        self.assertIsNone(result['input'])
        self.assertEqual(result['output'], 8)
        self.assertEqual(result['completeness'], 'partial')
        self.assertTrue(all(run.usage('')[key] is None for key in ('input', 'output', 'model')))

    def test_malformed_and_invalid_counts(self):
        for stream in ('[]\n', '{bad}\n', '{bad}\n{}'):
            with self.subTest(stream=stream), self.assertRaises(ValueError):
                run.usage(stream)
        for count in (True, -1, '1', 1.5):
            result = run.usage(fixture(usage={'input_tokens': count}))
            self.assertIsNone(result['input'])
            self.assertEqual(result['completeness'], 'partial')

    def test_join_pricing_uses_ledger_subscription_semantics(self):
        row = dict(model='synthetic-model', inputTokens=100, cachedInputTokens=20,
                   cacheWriteInputTokens=0, outputTokens=5, pricing_date='2000-01-01',
                   source_url='https://models.dev', costTotal=0, cost_is_plan=True)
        result = run.usage(fixture(), row)
        self.assertIsNone(result['est_cost_usd'])
        self.assertIsNone(result['billed_cost_usd'])
        result = run.usage(fixture(), dict(row, api_equivalent_usd=0.25))
        self.assertEqual(result['est_cost_usd'], 0.25)
        self.assertEqual(result['subscription_equivalent_usd'], 0.25)
        self.assertIsNone(result['billed_cost_usd'])
        result = run.usage(fixture(), dict(row, cost_is_plan=False, costTotal=0.5,
                                          billed_cost_usd=0.4))
        self.assertEqual(result['est_cost_usd'], 0.5)
        self.assertEqual(result['billed_cost_usd'], 0.4)
        self.assertIsNone(result['subscription_equivalent_usd'])
        for change in ({'pricing_date': ''}, {'source_url': ''}, {'model': 'other'},
                       {'inputTokens': 99}, {'costTotal': -1, 'cost_is_plan': False},
                       {'billed_cost_usd': True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                run.usage(fixture(), dict(row, **change))


if __name__ == '__main__':
    unittest.main()
