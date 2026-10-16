#!/usr/bin/env python3
"""Offline OpenAPI array-uniqueness compatibility checks. Standard library only."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys

PREVIOUS = Path(__file__).resolve().parents[1] / 'constcheck' / 'constcheck.py'
spec = importlib.util.spec_from_file_location('uniquecheck_const', PREVIOUS)
const = importlib.util.module_from_spec(spec)
spec.loader.exec_module(const)
api = const.api


def unique(schema):
    value = schema.get('uniqueItems', False)
    api.require(type(value) is bool, 'uniqueItems must be a JSON boolean')
    return value


def excludes_arrays(schema):
    value = schema.get('type')
    return value is not None and (value != 'array' if isinstance(value, str)
                                  else 'array' not in value)


class Analyzer(const.Analyzer):
    def _schema(self, old, new, loc, direction):
        super()._schema(old, new, loc, direction)
        before, after = unique(old), unique(new)
        # Inapplicable to explicitly non-array schemas on both sides. Keep the
        # inherited review finding; do not infer satisfiability of other keywords.
        if excludes_arrays(old) and excludes_arrays(new):
            return
        unsafe = (not before and after) if direction == 'request' else (before and not after)
        if unsafe:
            self.emit('breaking', 'unique_items_incompatible', loc + '/uniqueItems',
                      'New request uniqueness rule can reject arrays containing duplicate values.'
                      if direction == 'request' else
                      'New response rule can allow duplicate array values old clients excluded.')


def compare(old, new):
    report = Analyzer(old, new).run()
    report['extension'] = 'uniquecheck-v1 (includes constcheck-v1, multiplecheck-v1, boundcheck-v1)'
    return report


def demo():
    old, digest = api.load(const.multiple.bound.BASE.with_name('imd-openapi.json'))
    old = copy.deepcopy(old)
    schema = old['paths']['/requests/quote']['post']['requestBody']['content']['application/json']['schema']
    schema.setdefault('properties', {})['clientTags25'] = {
        'type': 'array', 'items': {'type': 'string'}}
    new = copy.deepcopy(old)
    new['paths']['/requests/quote']['post']['requestBody']['content']['application/json']['schema']['properties']['clientTags25']['uniqueItems'] = True
    report = compare(old, new)
    report.update(capture_sha256=digest,
                  demo='Hypothetical uniqueness change in the captured public IMD description; no operation called.',
                  illustrative_old_request={'clientTags25': ['urgent', 'urgent']})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('demo')
    diff = commands.add_parser('compare')
    diff.add_argument('old')
    diff.add_argument('new')
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            report = demo()
        else:
            old, oh = api.load(args.old)
            new, nh = api.load(args.new)
            report = compare(old, new)
            report.update(old_sha256=oh, new_sha256=nh)
        print(json.dumps(report, indent=2, allow_nan=False))
        return 0 if args.command == 'demo' else {
            'breaking': 1, 'review_required': 3, 'no_detected_breakage': 0}[report['status']]
    except (api.Invalid, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        print('uniquecheck: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
