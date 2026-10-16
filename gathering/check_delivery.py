#!/usr/bin/env python3
"""Check delivery bytes, source integrity and gallery coverage without network."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib


def digest(data):
    return hashlib.sha256(data).hexdigest()


def png(data, flatten_alpha=False):
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    offset, packed, header = 8, bytearray(), None
    while offset < len(data):
        size = struct.unpack('>I', data[offset:offset+4])[0]
        kind, payload = data[offset+4:offset+8], data[offset+8:offset+8+size]
        crc = struct.unpack('>I', data[offset+8+size:offset+12+size])[0]
        assert zlib.crc32(kind + payload) & 0xffffffff == crc
        if kind == b'IHDR':
            header = struct.unpack('>IIBBBBB', payload)
        elif kind == b'IDAT':
            packed.extend(payload)
        offset += size + 12
        if kind == b'IEND':
            break
    width, height, depth, color, compression, filtering, interlace = header
    assert depth == 8 and color in (2, 6) and (compression, filtering, interlace) == (0, 0, 0)
    channels = 3 if color == 2 else 4
    stride = width * channels
    raw = zlib.decompress(packed)
    assert len(raw) == height * (stride + 1)
    result, prior = bytearray(), bytearray(stride)
    for y in range(height):
        offset = y * (stride + 1)
        mode, row = raw[offset], bytearray(raw[offset+1:offset+1+stride])
        assert 0 <= mode <= 4
        for i in range(stride):
            a = row[i-channels] if i >= channels else 0
            b = prior[i]
            c = prior[i-channels] if i >= channels else 0
            if mode == 1:
                value = a
            elif mode == 2:
                value = b
            elif mode == 3:
                value = (a+b)//2
            elif mode == 4:
                p = a+b-c
                pa, pb, pc = abs(p-a), abs(p-b), abs(p-c)
                value = a if pa <= pb and pa <= pc else b if pb <= pc else c
            else:
                value = 0
            row[i] = (row[i] + value) & 255
        if channels == 3:
            result.extend(row)
        else:
            assert flatten_alpha or all(row[i] == 255 for i in range(3, len(row), 4)), 'input alpha must be opaque'
            for i in range(0, len(row), 4):
                alpha = row[i+3] / 255
                result.extend(round(c * alpha + 255 * (1-alpha)) for c in row[i:i+3])
        prior = row
    return (width, height), result


def jpeg_dimensions(data):
    assert data[:2] == b'\xff\xd8' and data[-2:] == b'\xff\xd9'
    offset = 2
    while offset < len(data):
        assert data[offset] == 255
        while data[offset] == 255:
            offset += 1
        marker = data[offset]
        offset += 1
        size = int.from_bytes(data[offset:offset+2], 'big')
        if marker in (0xc0, 0xc1, 0xc2):
            height, width = struct.unpack('>HH', data[offset+3:offset+7])
            return width, height
        offset += size
    raise AssertionError('JPEG has no supported frame')


def main():
    root = Path(__file__).resolve().parent.parent
    assert Path.cwd().resolve() == root, 'run from repository root'
    expected = json.loads(Path('gathering/line-integrity-22.json').read_text())
    actual = {str(p): digest(p.read_bytes()) for n in range(1, 5)
              for folder in (Path(f'line-{n}'), Path(f'dist/line-{n}'))
              for p in folder.rglob('*') if p.is_file()}
    assert expected == actual, 'line sources/records/previews changed'
    wall = Path('artifacts/gathering/wall-v3.png').read_bytes()
    canonical = Path('artifacts/gathering/wall.png')
    assert canonical.is_symlink() and canonical.readlink() == Path('wall-v3.png')
    assert not Path('artifacts/gathering/wall-v3.png').is_symlink()
    assert wall == canonical.read_bytes()
    dimensions, pixels = png(wall)
    assert dimensions == (1254, 1254)
    # The input-region digest was captured and checked against the inherited wall
    # during creation. It survives a new Git HEAD without shipping an extra image.
    preservation = json.loads(Path('gathering/preservation-22.json').read_text())
    protected = hashlib.sha256()
    for y in range(1254):
        row = pixels[y*1254*3:(y+1)*1254*3]
        if 175 <= y < 375:
            protected.update(row[:500*3])
            protected.update(row[720*3:])
        else:
            protected.update(row)
    assert protected.hexdigest() == preservation['protected_rgb_sha256'], 'ancestor/background pixels changed'
    assert digest(wall) == preservation['output_sha256']
    preview = Path('dist/gathering/22.jpg').read_bytes()
    assert jpeg_dimensions(preview) == (512, 512) and len(preview) < 100000
    record = json.loads(Path('dist/gathering/22.json').read_text())
    assert list(record) == ['name', 'image', 'attributes']
    assert record['image'] == 'https://api.imd.fun/artifacts/' + digest(wall)
    traits = {a['trait_type']: a['value'] for a in record['attributes']}
    assert set(traits) == {'Cave', 'Wall', 'Number', 'Left behind', 'Meaning', 'One thing'}
    assert traits['Cave'] == 'Lava' and traits['Wall'] == traits['One thing'] == 'Gathering'
    assert type(traits['Number']) is int and traits['Number'] == 22
    goals = [{'line': n, 'goal': Path(f'line-{n}/GOAL.md').read_text().strip()} for n in range(1, 5)]
    assert json.loads(Path('dist/goals.json').read_text()) == goals
    page = Path('dist/index.html').read_text()
    count = 0
    for folder in [f'line-{n}' for n in range(1, 5)] + ['gathering']:
        for path in Path('dist', folder).glob('*.json'):
            assert f'href="{folder}/{path.name}"' in page, str(path) + ' absent from gallery'
            count += 1
        for n in range(2, 22):
            path = Path('dist', folder, f'{n:02}.json')
            assert json.loads(path.read_text())['name'] == 'Not painted yet'
            assert not path.with_suffix('.jpg').exists()
        assert page.index(f'href="{folder}/22.json"') < page.index(f'href="{folder}/01.json"')
    sources = json.loads(Path('shared/api_bundle/SOURCES.json').read_text())
    for file, info in sources.items():
        assert digest(Path('shared/api_bundle', file).read_bytes()) == info['sha256']
        assert digest(Path(info['source']).read_bytes()) == info['source_sha256']
    for row in json.loads(Path('gathering/check-results-22.json').read_text()) + json.loads(Path('gathering/integration-results-22.json').read_text()):
        assert row['passed'] and row['exit'] == row['expected_exit']
    status = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=all'],
                            capture_output=True, text=True, check=True).stdout
    paths = [line[3:] for line in status.splitlines()]
    allowed = ('gathering/', 'shared/', 'artifacts/gathering/', 'dist/', 'test/scratch/')
    for path in paths:
        assert path.startswith(allowed), 'out-of-scope path: ' + path
        p = Path(path)
        if p.is_file() and not path.startswith(('artifacts/', 'test/scratch/')):
            assert p.stat().st_size <= 100000, 'file over 100 KB: ' + path
    result = dict(passed=True, line_files_unchanged=len(actual), gallery_records=count,
                  png_dimensions=list(dimensions), jpeg_dimensions=[512, 512],
                  png_sha256=digest(wall), jpeg_bytes=len(preview),
                  changed_pixels_at_creation=preservation['changed_pixels'],
                  protected_rgb_sha256=protected.hexdigest(), protected_pixels_match=True,
                  source_hashes_checked=True, all_recorded_exits_match=True,
                  changed_paths_in_scope=True, unpainted_slots_preserved=100,
                  limitation='Structural and byte checks do not certify visual quality or tool behavior.')
    Path('gathering/delivery-check-22.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
