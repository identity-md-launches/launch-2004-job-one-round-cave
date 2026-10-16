"""Independent finite acceptance oracle and integration regressions."""
import copy
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uniquecheck as u


def document(schema, response=False, version='3.1.0'):
    media = {'application/json': {'schema': schema}}
    op = {'responses': {'200': {'description': 'ok', 'content': media if response else {}}}}
    if not response:
        op['requestBody'] = {'content': media}
    return {'openapi': version, 'paths': {'/items': {'post': op}}}


def hits(old, new, response=False, version='3.1.0'):
    return [f for f in u.compare(document(old, response, version),
                                document(new, response, version))['findings']
            if f['code'] == 'unique_items_incompatible']


class Tests(unittest.TestCase):
    def test_finite_acceptance_oracle(self):
        # Enumerate all arrays up to length 3 over two values. Derive the break
        # from accepted sets, independently of the implementation's rule.
        arrays = [a for size in range(4) for a in itertools.product((0, 1), repeat=size)]
        options = ({}, {'uniqueItems': False}, {'uniqueItems': True})
        def accepted(schema):
            return {a for a in arrays if not schema.get('uniqueItems', False)
                    or len(a) == len(set(a))}
        for version, response, old, new in itertools.product(
                ('3.0.3', '3.1.0'), (False, True), options, options):
            before, after = accepted(old), accepted(new)
            expected = bool(after - before if response else before - after)
            with self.subTest(version=version, response=response, old=old, new=new):
                self.assertEqual(bool(hits(dict(type='array', **old),
                                           dict(type='array', **new), response, version)), expected)

    def test_unspecified_and_union_types(self):
        for kind in (None, ['array', 'null'], ['array']):
            old = {} if kind is None else {'type': kind}
            self.assertTrue(hits(old, dict(old, uniqueItems=True)))
            self.assertTrue(hits(dict(old, uniqueItems=True), old, True))

    def test_explicit_nonarrays_keep_review(self):
        for kind in ('string', ['string', 'null'], 'object', 'integer'):
            old, new = {'type': kind}, {'type': kind, 'uniqueItems': True}
            self.assertFalse(hits(old, new))
            self.assertEqual(u.compare(document(old), document(new))['status'], 'review_required')

    def test_malformed_booleans_rejected_when_visited(self):
        for value in (0, 1, 'true', None, [], {}):
            for response in (False, True):
                with self.subTest(value=value, response=response):
                    with self.assertRaises(u.api.Invalid):
                        hits({'type': 'array'}, {'type': 'array', 'uniqueItems': value}, response)

    def test_refs_recursion_escaped_location(self):
        old = document({'$ref': '#/components/schemas/N'})
        old['components'] = {'schemas': {'N': {'properties': {
            'next': {'$ref': '#/components/schemas/N'},
            'tags/~': {'type': 'array', 'items': {'type': 'string'}}}}}}
        new = copy.deepcopy(old)
        new['components']['schemas']['N']['properties']['tags/~']['uniqueItems'] = True
        report = u.compare(old, new)
        found = [f for f in report['findings'] if f['code'] == 'unique_items_incompatible']
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]['location'].endswith('/tags~1~0/uniqueItems'))

    def test_nested_array_items(self):
        old = {'type': 'array', 'items': {'type': 'array'}}
        new = copy.deepcopy(old)
        new['items']['uniqueItems'] = True
        self.assertTrue(hits(old, new)[0]['location'].endswith('/items/uniqueItems'))

    def test_relaxations_and_default_still_review(self):
        for old, new, response in (({'uniqueItems': True}, {}, False),
                                   ({}, {'uniqueItems': True}, True),
                                   ({}, {'uniqueItems': False}, False)):
            report = u.compare(document(old, response), document(new, response))
            self.assertEqual(report['status'], 'review_required')
            self.assertFalse(hits(old, new, response))

    def test_inherited_rules(self):
        old = {'type': 'array', 'minItems': 1, 'const': ['x'], 'uniqueItems': False}
        new = {'type': 'array', 'minItems': 2, 'const': ['y'], 'uniqueItems': True}
        codes = {f['code'] for f in u.compare(document(old), document(new))['findings']}
        self.assertTrue({'unique_items_incompatible', 'size_bound_incompatible',
                         'const_incompatible', 'schema_constraint_changed'} <= codes)
        codes = {f['code'] for f in u.compare(document({'multipleOf': 2}),
                                             document({'multipleOf': 3}))['findings']}
        self.assertIn('multiple_of_incompatible', codes)

    def test_capture_and_demo(self):
        obj, _ = u.api.load(u.const.multiple.bound.BASE.with_name('imd-openapi.json'))
        report = u.compare(obj, obj)
        self.assertEqual(report['operations_compared'], 5)
        self.assertEqual(report['findings'], [])
        report = u.demo()
        self.assertEqual(report['counts'], {'breaking': 1, 'review': 1, 'info': 0})

    def test_cli_exits_and_hashes(self):
        root = Path('test/scratch')
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            old, new = Path(folder) / 'old.json', Path(folder) / 'new.json'
            old.write_text(json.dumps(document({'uniqueItems': True})))
            script = str(Path(__file__).with_name('uniquecheck.py'))
            for schema, expected in (({'uniqueItems': True}, 0),
                                     ({'uniqueItems': False}, 3), ({'const': 'x'}, 1),
                                     ({'uniqueItems': 'true'}, 2)):
                new.write_text(json.dumps(document(schema)))
                result = subprocess.run([sys.executable, '-B', script, 'compare', str(old), str(new)],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, expected, result.stderr)
                if expected != 2:
                    self.assertEqual(len(json.loads(result.stdout)['old_sha256']), 64)
            new.write_text('{"openapi":"3.1.0","paths":{},"paths":{}}')
            result = subprocess.run([sys.executable, '-B', script, 'compare', str(old), str(new)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
