#!/usr/bin/env python3
"""Independently check a fresh, full offline work schedule; execute no tasks."""
import argparse
from decimal import Decimal
from fractions import Fraction
import json
from pathlib import Path
import stat
import sys

LIMIT = 100000


def number(value, label):
    # Decimal spelling is exact. Limit exponent/size before constructing Fraction.
    if type(value) not in (int, float, Decimal):
        raise ValueError(label + ' must be a finite number')
    d = Decimal(str(value))
    if not d.is_finite() or abs(d.as_tuple().exponent) > 100 or len(d.as_tuple().digits) > 100:
        raise ValueError(label + ' exceeds finite 100-digit/100-exponent limits')
    return Fraction(d)


def keys(row, required, optional=()):
    if not isinstance(row, dict) or not set(required) <= row.keys() or row.keys() - set(required) - set(optional):
        raise ValueError('expected fields: ' + ', '.join(required))


def graph(data):
    keys(data, ('tasks',))
    if not isinstance(data['tasks'], list) or not 1 <= len(data['tasks']) <= 500:
        raise ValueError('tasks must contain 1 to 500 entries')
    tasks = {}
    for row in data['tasks']:
        keys(row, ('id', 'minutes'), ('after',))
        name = row['id']
        if not isinstance(name, str) or not name.strip() or len(name) > 100 or name in tasks:
            raise ValueError('invalid or duplicate task id')
        duration = number(row['minutes'], 'minutes')
        if duration <= 0:
            raise ValueError('minutes must be positive')
        deps = row.get('after', [])
        if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps) or len(set(deps)) != len(deps):
            raise ValueError('after must contain distinct task ids')
        tasks[name] = (duration, deps)
    children = {name: [] for name in tasks}
    degree = {name: len(deps) for name, (_, deps) in tasks.items()}
    for name, (_, deps) in tasks.items():
        for dep in deps:
            if dep not in tasks:
                raise ValueError('unknown dependency: ' + dep)
            children[dep].append(name)
    ready = [name for name in tasks if degree[name] == 0]
    visited = 0
    while ready:
        name = ready.pop()
        visited += 1
        for child in children[name]:
            degree[child] -= 1
            if degree[child] == 0:
                ready.append(child)
    if visited != len(tasks):
        raise ValueError('dependency cycle')
    return tasks


def check(data, proposed, workers, budget=None):
    """Check only a complete schedule from time zero, independent of its producer.

    The external workers/budget are authoritative; planner optimality and lower
    bound claims are deliberately not certified. Invalid schemas raise ValueError;
    well-formed but infeasible schedules return valid=False with violations.
    """
    if type(workers) is not int or not 1 <= workers <= 64:
        raise ValueError('workers must be an integer from 1 to 64')
    deadline = None if budget is None else number(budget, 'budget')
    if deadline is not None and deadline < 0:
        raise ValueError('budget must be nonnegative')
    tasks = graph(data)
    if not isinstance(proposed, dict) or not {'schedule', 'finish', 'workers'} <= proposed.keys():
        raise ValueError('plan needs schedule, finish and workers')
    if type(proposed['workers']) is not int:
        raise ValueError('plan workers must be an integer')
    claimed_finish = number(proposed['finish'], 'finish')
    rows = proposed['schedule']
    if not isinstance(rows, list) or len(rows) > 500:
        raise ValueError('schedule must be an array of at most 500 entries')
    issues, slots, by_worker = [], {}, {}
    if proposed.get('units', 'minutes') != 'minutes':
        issues.append('units_mismatch')
    if proposed['workers'] != workers:
        issues.append('worker_count_mismatch')
    for row in rows:
        # Replan remaining segments intentionally rejected: this checks full jobs.
        keys(row, ('task', 'worker', 'start', 'finish'))
        name, worker = row['task'], row['worker']
        if not isinstance(name, str) or type(worker) is not int:
            raise ValueError('task must be a string and worker an integer')
        start, end = number(row['start'], 'start'), number(row['finish'], 'finish')
        if name not in tasks:
            issues.append('unknown_task:' + name)
        if name in slots:
            issues.append('duplicate_task:' + name)
        else:
            slots[name] = (worker, start, end)
        if not 1 <= worker <= workers:
            issues.append('worker_out_of_range:' + name)
        if start < 0 or end <= start:
            issues.append('invalid_interval:' + name)
        if name in tasks and end - start != tasks[name][0]:
            issues.append('duration_mismatch:' + name)
        by_worker.setdefault(worker, []).append((start, end, name))
    for name in sorted(tasks):
        if name not in slots:
            issues.append('missing_task:' + name)
            continue
        for dep in sorted(tasks[name][1]):
            if dep in slots and slots[dep][2] > slots[name][1]:
                issues.append('dependency_violation:' + dep + '->' + name)
    # Keep the latest finish, not merely the preceding row: nested overlaps count.
    for worker in sorted(by_worker):
        latest = None
        for start, end, name in sorted(by_worker[worker]):
            if latest is not None and start < latest:
                issues.append('worker_overlap:' + str(worker) + ':' + name)
            latest = end if latest is None else max(latest, end)
    actual_finish = max((end for group in by_worker.values() for _, end, _ in group), default=Fraction(0))
    if claimed_finish != actual_finish or claimed_finish < 0:
        issues.append('finish_mismatch')
    if deadline is not None and actual_finish > deadline:
        issues.append('deadline_exceeded')
    return {'valid': not issues, 'violations': sorted(issues),
            'tasks_expected': len(tasks), 'schedule_entries': len(rows),
            'workers_checked': workers, 'deadline_checked': deadline is not None,
            'arithmetic': 'exact decimal values; no tolerance',
            'scope': 'full schedule feasibility at supplied estimates; no execution or optimality proof'}


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(filename):
    path = Path(filename).resolve()
    root = Path.cwd().resolve()
    if not path.is_relative_to(root) or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('input must be an ordinary file inside the workspace')
    with path.open('rb') as handle:
        raw = handle.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('input exceeds 100 KB')
    return json.loads(raw, parse_float=Decimal, object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON number')))


def demo():
    data = {'tasks': [{'id': 'read', 'minutes': 2},
                      {'id': 'build', 'minutes': 5, 'after': ['read']},
                      {'id': 'fixtures', 'minutes': 3, 'after': ['read']},
                      {'id': 'check', 'minutes': 2, 'after': ['build', 'fixtures']}]}
    plan = {'workers': 2, 'finish': 9, 'schedule': [
        {'task': 'read', 'worker': 1, 'start': 0, 'finish': 2},
        {'task': 'build', 'worker': 1, 'start': 2, 'finish': 7},
        {'task': 'fixtures', 'worker': 2, 'start': 2, 'finish': 5},
        {'task': 'check', 'worker': 1, 'start': 7, 'finish': 9}]}
    valid = check(data, plan, 2, 10)
    plan['schedule'][-1].update(start=5, finish=7)
    plan['finish'] = 7
    rejected = check(data, plan, 2, 10)
    return {'valid_example': valid, 'tampered_example': rejected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--tasks')
    parser.add_argument('--plan')
    parser.add_argument('--workers', type=int)
    parser.add_argument('--budget', type=Decimal)
    args = parser.parse_args()
    try:
        if args.demo:
            if any(x is not None for x in (args.tasks, args.plan, args.workers, args.budget)):
                raise ValueError('--demo cannot be combined with file/check options')
            result = demo()
            code = 0
        else:
            if args.tasks is None or args.plan is None or args.workers is None:
                raise ValueError('--tasks, --plan and --workers are required')
            result = check(read_json(args.tasks), read_json(args.plan), args.workers, args.budget)
            code = 0 if result['valid'] else 2
        print(json.dumps(result, indent=2, allow_nan=False))
        return code
    except (ValueError, OSError, RecursionError, OverflowError) as exc:
        print('plancheck: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
