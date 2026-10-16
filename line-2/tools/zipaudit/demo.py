#!/usr/bin/env python3
"""Replay a real public-data extraction and detect subsequent byte tampering."""
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile
from zipaudit import audit, local_path, process, Rejected


def main():
    sample = local_path(Path(__file__).resolve().parents[1] / 'safezip/imd-openapi.json')
    with sample.open('rb') as reader:
        data = reader.read(65537)
    if hashlib.sha256(data).hexdigest() != 'be142840c010710cb2a5b9e5c73e71d8e79ec4054c15661699d60bfa627be96a':
        raise ValueError('bundled public capture differs')
    scratch = local_path('test/scratch')
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix='zipaudit-demo-') as temp:
        root = Path(temp)
        archive, tree = root / 'capture.zip', root / 'extracted'
        name = 'docs/imd/openapi.json'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr(zipfile.ZipInfo(name), data, compress_type=zipfile.ZIP_DEFLATED)
        digest = process(archive)['archive_sha256']
        process(archive, tree, expected_sha256=digest, nodes=3, seconds=10)
        before = audit(archive, tree, expected_sha256=digest, nodes=3, seconds=10)
        # Deliberate same-size damage of disposable output, never the capture.
        changed = bytearray(data)
        changed[len(changed) // 2] ^= 1
        (tree / name).write_bytes(changed)
        try:
            audit(archive, tree, expected_sha256=digest, nodes=3, seconds=10)
        except Rejected as error:
            refusal = str(error)
        else:
            raise AssertionError('same-size damage was missed')
        print(json.dumps({'ok': True, 'network_used': False,
                          'source': 'https://api.imd.fun/openapi.json',
                          'source_bytes': len(data), 'before': before,
                          'same_size_damage_rejected': refusal}, indent=2))


if __name__ == '__main__':
    main()
