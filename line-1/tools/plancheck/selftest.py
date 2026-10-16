#!/usr/bin/env python3
"""Independent feasibility and adversarial tests; disposable files stay in scratch."""
import copy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys
import unittest

import plancheck as pc

HERE = Path(__file__).resolve().parent
ROOT = Path.cwd()
SCRATCH = ROOT / 'test/scratch/plancheck'


def load_tool(name):
    p = HERE.parent / name / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Checks(unittest.TestCase):
    def setUp(self):
        self.data = {'tasks': [{'id': 'a', 'minutes': 3},
                               {'id': 'b', 'minutes': 2, 'after': ['a']}]}
        self.plan = {'workers': 2, 'finish': 5, 'schedule': [
            {'task': 'a', 'worker': 1, 'start': 0, 'finish': 3},
            {'task': 'b', 'worker': 2, 'start': 3, 'finish': 5}]}

    def check(self, budget=None):
        return pc.check(self.data, self.plan, 2, budget)

    def test_demo(self):
        result = pc.demo()
        self.assertTrue(result['valid_example']['valid'])
        self.assertEqual(result['tampered_example']['violations'],
                         ['dependency_violation:build->check', 'worker_overlap:1:check'])

    def test_valid_and_immutable(self):
        original = copy.deepcopy((self.data, self.plan))
        self.assertTrue(self.check(5)['valid'])
        self.assertEqual(original, (self.data, self.plan))
        self.plan['schedule'].reverse()
        self.data['tasks'].reverse()
        self.assertTrue(self.check()['valid'])

    def test_coverage(self):
        self.plan['schedule'].pop()
        self.assertIn('missing_task:b', self.check()['violations'])
        self.plan['schedule'].append(copy.deepcopy(self.plan['schedule'][0]))
        self.assertIn('duplicate_task:a', self.check()['violations'])
        self.plan['schedule'][-1]['task'] = 'unknown'
        self.assertIn('unknown_task:unknown', self.check()['violations'])

    def test_dependency(self):
        self.plan['schedule'][-1].update(start=2, finish=4)
        self.plan['finish'] = 4
        self.assertEqual(self.check()['violations'], ['dependency_violation:a->b'])

    def test_durations_and_intervals(self):
        self.plan['schedule'][0]['finish'] = 2
        self.assertIn('duration_mismatch:a', self.check()['violations'])
        self.plan['schedule'][0].update(start=-1, finish=2)
        self.assertIn('invalid_interval:a', self.check()['violations'])
        self.plan['schedule'][0].update(start=2, finish=2)
        self.assertIn('invalid_interval:a', self.check()['violations'])

    def test_worker_and_units(self):
        self.plan['workers'] = 3
        self.plan['schedule'][0]['worker'] = 0
        self.plan['units'] = 'seconds'
        result = self.check()['violations']
        self.assertIn('worker_count_mismatch', result)
        self.assertIn('worker_out_of_range:a', result)
        self.assertIn('units_mismatch', result)

    def test_nested_worker_overlaps(self):
        self.data = {'tasks': [{'id': 'a', 'minutes': 10}, {'id': 'b', 'minutes': 1},
                               {'id': 'c', 'minutes': 1}]}
        self.plan = {'workers': 2, 'finish': 10, 'schedule': [
            {'task': 'a', 'worker': 1, 'start': 0, 'finish': 10},
            {'task': 'b', 'worker': 1, 'start': 1, 'finish': 2},
            {'task': 'c', 'worker': 1, 'start': 3, 'finish': 4}]}
        self.assertEqual(self.check()['violations'], ['worker_overlap:1:b', 'worker_overlap:1:c'])

    def test_deadline_and_untrusted_claims(self):
        self.plan.update(fits_budget=True, proven_optimal=True, lower_bound=0, budget=999)
        self.assertEqual(self.check(4)['violations'], ['deadline_exceeded'])
        self.plan['finish'] = 1
        self.assertIn('finish_mismatch', self.check()['violations'])
        self.assertIn('deadline_exceeded', self.check(0)['violations'])

    def test_idle_is_valid(self):
        for row in self.plan['schedule']:
            row['start'] += 10
            row['finish'] += 10
        self.plan['finish'] += 10
        self.assertTrue(self.check(15)['valid'])

    def test_exact_decimal(self):
        self.data = {'tasks': [{'id': 'a', 'minutes': Decimal('0.1')},
                               {'id': 'b', 'minutes': Decimal('0.2'), 'after': ['a']}]}
        self.plan['finish'] = Decimal('0.3')
        self.plan['schedule'][0].update(start=0, finish=Decimal('0.1'))
        self.plan['schedule'][1].update(start=Decimal('0.1'), finish=Decimal('0.3'))
        self.assertTrue(self.check(Decimal('0.3'))['valid'])
        self.plan['schedule'][1]['finish'] = Decimal('0.30000000000000004')
        self.assertIn('duration_mismatch:b', self.check()['violations'])

    def test_bad_graphs(self):
        for bad in [[], {'tasks': []}, {'tasks': [{'id': 'x', 'minutes': True}]},
                    {'tasks': [{'id': 'x', 'minutes': 0}]},
                    {'tasks': [{'id': 'x', 'minutes': 1, 'after': ['x']}]},
                    {'tasks': [{'id': 'x', 'minutes': 1, 'after': ['y']}]},
                    {'tasks': [{'id': 'x', 'minutes': 1, 'after': ['y','y']}]},
                    {'tasks': [{'id': 'x', 'minutes': 1}]*2},
                    {'tasks': [{'id': 'x', 'minutes': 1, 'command': 'ignored'}]}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                pc.check(bad, self.plan, 2)

    def test_bad_values_and_progress(self):
        for value in [True, '1', float('nan'), float('inf'), Decimal('1e-1000000'), 10**101]:
            with self.subTest(value=str(value)[:20]), self.assertRaises(ValueError):
                pc.number(value, 'number')
        for workers in [True, 0, 65, 1.5]:
            with self.assertRaises(ValueError):
                pc.check(self.data, self.plan, workers)
        self.plan['schedule'][0]['state'] = 'running'
        with self.assertRaises(ValueError):
            self.check()

    def test_read_boundary(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        path = SCRATCH / 'input.json'
        for raw in ['{"tasks":[],"tasks":[]}', '{"n":NaN}', ' '*100001, '{}x']:
            path.write_text(raw)
            with self.assertRaises(ValueError):
                pc.read_json(path)
        path.write_text('{"value":0.1}')
        self.assertEqual(pc.read_json(path)['value'], Decimal('0.1'))
        with self.assertRaises(ValueError):
            pc.read_json(SCRATCH)
        # Resolving outside paths is rejected before opening or reading them.
        with self.assertRaises(ValueError):
            pc.read_json(ROOT.parent / 'outside-plancheck.json')

    def test_existing_planners(self):
        wp, op = load_tool('workplan'), load_tool('optplan')
        for data, result, workers in [(wp.demo(), wp.plan(wp.demo(), 2), 2),
                                      (op.demo(), op.exact(op.demo(), 2), 2),
                                      (op.idle_demo(), op.exact(op.idle_demo(), 2), 2)]:
            self.assertTrue(pc.check(data, result, workers)['valid'])
        rng = random.Random(73725)
        for _ in range(150):
            n, workers = rng.randint(1, 20), rng.randint(1, 5)
            data = {'tasks': [{'id': str(i), 'minutes': rng.randint(1, 20),
                              'after': [str(j) for j in range(i) if rng.random() < .15]}
                             for i in range(n)]}
            result = wp.plan(data, workers)
            self.assertTrue(pc.check(data, result, workers, result['finish'])['valid'])
            # A mutated duration must never be hidden by producer metadata.
            result['schedule'][0]['finish'] += 1
            self.assertFalse(pc.check(data, result, workers)['valid'])

    def test_cli(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        tasks, plan = SCRATCH / 'tasks.json', SCRATCH / 'plan.json'
        tasks.write_text(json.dumps(self.data))
        plan.write_text(json.dumps(self.plan))
        cmd = [sys.executable, '-B', str(HERE / 'plancheck.py'), '--tasks', str(tasks),
               '--plan', str(plan), '--workers', '2']
        for budget, expected in [('5', 0), ('4', 2), ('NaN', 1)]:
            result = subprocess.run(cmd + ['--budget', budget], capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)
            if expected == 1:
                self.assertEqual(result.stdout, '')
            else:
                self.assertEqual(json.loads(result.stdout)['valid'], expected == 0)
        result = subprocess.run([sys.executable, '-B', str(HERE / 'plancheck.py'), '--demo'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['tampered_example']['valid'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
