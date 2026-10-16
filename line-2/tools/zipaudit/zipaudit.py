#!/usr/bin/env python3
"""Read-only exact-tree audit against an approved ZIP. Standard library only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import zipfile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'safezip'))
from safezip import Rejected, local_path, process


def audit(archive, tree, *, expected_sha256, seconds=None, **limits):
    """Return success only for an exact tree; never repair or execute contents.

    All SafeZip resource limits apply to the reference ZIP. The expected tree
    then supplies exact bounds for filesystem traversal and file reads.
    """
    if expected_sha256 is None:
        raise Rejected('an approved archive SHA-256 is required')
    started = time.monotonic()
    reference = process(archive, expected_sha256=expected_sha256,
                        seconds=seconds, **limits)

    def checkpoint():
        if seconds is not None and time.monotonic() - started >= seconds:
            raise Rejected('audit time budget exceeded')

    checkpoint()
    root = local_path(tree)
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise Rejected('audit root must be a directory')
    expected = {}
    for entry in reference['entries']:
        parts = entry['path'].split('/')
        for length in range(1, len(parts)):
            expected['/'.join(parts[:length])] = {'kind': 'directory'}
        expected[entry['path']] = entry
    seen = set()
    pending = [(root, '')]
    checked_bytes = 0
    while pending:
        directory, prefix = pending.pop()
        checkpoint()
        # Iterate, rather than materializing an unbounded directory listing.
        with os.scandir(directory) as children:
            for child in children:
                checkpoint()
                name = prefix + child.name
                entry = expected.get(name)
                if entry is None:
                    raise Rejected('unexpected path: ' + repr(name))
                mode = child.stat(follow_symlinks=False).st_mode
                wanted = stat.S_ISDIR(mode) if entry['kind'] == 'directory' else stat.S_ISREG(mode)
                if not wanted:
                    raise Rejected('wrong type or link: ' + repr(name))
                seen.add(name)
                if entry['kind'] == 'directory':
                    pending.append((Path(child.path), name + '/'))
                    continue
                size = entry['bytes']
                if child.stat(follow_symlinks=False).st_size != size:
                    raise Rejected('size differs: ' + repr(name))
                digest = hashlib.sha256()
                count = 0
                with open(child.path, 'rb') as reader:
                    if not stat.S_ISREG(os.fstat(reader.fileno()).st_mode):
                        raise Rejected('file is no longer regular: ' + repr(name))
                    while True:
                        checkpoint()
                        chunk = reader.read(min(65536, size - count + 1))
                        if not chunk:
                            break
                        count += len(chunk)
                        if count > size:
                            raise Rejected('file grew: ' + repr(name))
                        digest.update(chunk)
                if count != size or digest.hexdigest() != entry['sha256']:
                    raise Rejected('content differs: ' + repr(name))
                checked_bytes += count
    missing = expected.keys() - seen
    if missing:
        raise Rejected('missing path: ' + repr(min(missing)))
    checkpoint()
    return {'ok': True, 'mode': 'audit', 'archive_sha256': reference['archive_sha256'],
            'nodes_checked': len(seen), 'bytes_checked': checked_bytes,
            'exact_tree': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive')
    parser.add_argument('tree')
    parser.add_argument('--sha256', required=True, help='previously approved ZIP digest')
    parser.add_argument('--seconds', type=float, default=None)
    for name, default in [('entries', 1000), ('nodes', 32000),
                          ('archive-bytes', 33554432), ('file-bytes', 16777216),
                          ('total-bytes', 67108864), ('ratio', 200)]:
        parser.add_argument('--' + name, type=int, default=default)
    args = vars(parser.parse_args())
    archive, tree = args.pop('archive'), args.pop('tree')
    args['expected_sha256'] = args.pop('sha256')
    try:
        result = audit(archive, tree, **args)
    except (ValueError, OSError, zipfile.BadZipFile, NotImplementedError,
            RuntimeError, EOFError, zlib.error) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=True))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
