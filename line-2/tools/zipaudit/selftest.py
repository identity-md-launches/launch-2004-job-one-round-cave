#!/usr/bin/env python3
"""Offline regression checks; disposable files stay under test/scratch/."""
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile
from zipaudit import audit, process, Rejected


class AuditTests(unittest.TestCase):
    def setUp(self):
        Path('test/scratch').mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir='test/scratch', prefix='zipaudit-')
        self.root = Path(self.tmp.name)
        self.archive = self.root / 'input.zip'
        self.tree = self.root / 'tree'
        with zipfile.ZipFile(self.archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('docs/imd/data.json', b'{"hello":"swarm"}\n')
            z.writestr('empty/', b'')
            z.writestr('zero', b'')
        self.digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        process(self.archive, self.tree, expected_sha256=self.digest)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, **kwargs):
        return audit(self.archive, self.tree, expected_sha256=self.digest, **kwargs)

    def test_exact_tree_with_implicit_and_empty_directories(self):
        result = self.check()
        self.assertTrue(result['exact_tree'])
        self.assertEqual(result['nodes_checked'], 5)
        self.assertEqual(result['bytes_checked'], 18)

    def test_same_size_change(self):
        (self.tree / 'docs/imd/data.json').write_bytes(b'{"hello":"SWARM"}\n')
        with self.assertRaisesRegex(Rejected, 'content differs'):
            self.check()

    def test_changed_size(self):
        (self.tree / 'zero').write_bytes(b'x')
        with self.assertRaisesRegex(Rejected, 'size differs'):
            self.check()

    def test_missing_file(self):
        (self.tree / 'zero').unlink()
        with self.assertRaisesRegex(Rejected, 'missing path'):
            self.check()

    def test_missing_empty_directory(self):
        (self.tree / 'empty').rmdir()
        with self.assertRaisesRegex(Rejected, 'missing path'):
            self.check()

    def test_extra_file_and_directory(self):
        for directory in (False, True):
            extra = self.tree / 'extra'
            if directory:
                extra.mkdir()
            else:
                extra.write_bytes(b'unexpected')
            with self.assertRaisesRegex(Rejected, 'unexpected path'):
                self.check()
            extra.rmdir() if directory else extra.unlink()

    def test_symlink_file_and_directory(self):
        for name, target in [('zero', self.archive.resolve()), ('empty', self.root.resolve())]:
            path = self.tree / name
            path.rmdir() if path.is_dir() else path.unlink()
            path.symlink_to(target)
            with self.assertRaisesRegex(Rejected, 'wrong type or link'):
                self.check()
            path.unlink()
            path.mkdir() if name == 'empty' else path.touch()

    def test_type_swap(self):
        (self.tree / 'zero').unlink()
        (self.tree / 'zero').mkdir()
        with self.assertRaisesRegex(Rejected, 'wrong type'):
            self.check()

    def test_root_symlink(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.tree.resolve(), target_is_directory=True)
        with self.assertRaisesRegex(Rejected, 'symlink'):
            audit(self.archive, alias, expected_sha256=self.digest)

    def test_approval_required_and_bound(self):
        for digest in (None, '', 'xyz', 'f' * 64):
            with self.assertRaises(Rejected):
                audit(self.archive, self.tree, expected_sha256=digest)
        self.assertTrue(audit(self.archive, self.tree,
                              expected_sha256=self.digest.upper())['ok'])

    def test_reference_limits(self):
        for options in ({'nodes': 4}, {'entries': 2}, {'file_bytes': 1},
                        {'archive_bytes': 1}, {'total_bytes': 1}, {'nodes': True}):
            with self.assertRaises(Rejected):
                self.check(**options)

    def test_cooperative_deadline_in_tree(self):
        real = __import__('os').scandir
        clock = [0.0]
        def scan(path):
            clock[0] = 11.0
            return real(path)
        with mock.patch('zipaudit.time.monotonic', side_effect=lambda: clock[0]), \
                mock.patch('zipaudit.os.scandir', side_effect=scan):
            with self.assertRaisesRegex(Rejected, 'audit time budget'):
                self.check(seconds=10)

    def test_invalid_seconds(self):
        for seconds in (0, True, float('nan'), float('inf')):
            with self.assertRaises(Rejected):
                self.check(seconds=seconds)

    def test_empty_archive(self):
        archive = self.root / 'empty.zip'
        with zipfile.ZipFile(archive, 'w'):
            pass
        tree = self.root / 'empty-tree'
        tree.mkdir()
        result = audit(archive, tree,
                       expected_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(result['nodes_checked'], 0)

    def test_no_mutation(self):
        def snapshot():
            return {str(p.relative_to(self.tree)): (p.stat().st_mode,
                    p.read_bytes() if p.is_file() else None)
                    for p in self.tree.rglob('*')}
        before = snapshot()
        self.check()
        self.assertEqual(before, snapshot())
        (self.tree / 'zero').write_bytes(b'changed')
        before = snapshot()
        with self.assertRaises(Rejected):
            self.check()
        self.assertEqual(before, snapshot())

    def test_cli(self):
        command = [sys.executable, '-B', str(Path(__file__).with_name('zipaudit.py')),
                   str(self.archive), str(self.tree), '--sha256', self.digest]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['exact_tree'])
        (self.tree / 'zero').unlink()
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)['ok'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
