# Plancheck

Independently check a full offline schedule before handing it to a worker.
Plancheck recomputes task coverage, durations, dependency ordering, worker
nonoverlap, makespan and an optional external deadline. It does not call a
scheduler or trust its feasibility claims. Python 3.9+, standard library only;
no install, network, task execution, environment access, keys or wallets.

From the repository root, run:

```sh
python3 -B line-1/tools/plancheck/plancheck.py --demo
```

Observed in round 25: a four-task schedule finishing at minute 9 under a
10-minute deadline returns `valid: true`. Moving its final check to minute 5
returns `valid: false`, with both `dependency_violation:build->check` and
`worker_overlap:1:check`. The demo exits 0 because it demonstrates both outcomes.
The times are illustrative estimates, not measured work.

## Check your own schedule

```sh
python3 -B line-1/tools/plancheck/plancheck.py --tasks line-1/tools/plancheck/tasks.json --plan line-1/tools/plancheck/plan.json --workers 2 --budget 5
```

This supplied file example is valid and exits 0. Changing the budget to 4 exits
2 with `deadline_exceeded`, regardless of the producer's own budget or claims.

The task input is the Workplan/Optplan shape:

```json
{"tasks":[{"id":"a","minutes":3},{"id":"b","minutes":2,"after":["a"]}]}
```

The plan input needs `workers`, `finish`, and `schedule`. Every schedule row
has exactly `task`, `worker`, `start`, `finish`. Workers are integer ids 1 through
the externally supplied worker count (1–64). Times are minutes since job start.
Intentional idle time and simultaneous end/start boundaries are allowed.
There must be exactly one positive-duration segment for every task.

Workplan and Optplan outputs can be read directly. Plan-level extra metadata
is ignored, except that `units`, if present, must be `minutes`; `workers` and
`finish` are checked against the actual rows and external worker count. Neither
`fits_budget`, `proven_optimal`, `lower_bound` nor a producer's `budget` grants
approval. The optional external `--budget` is the deadline being checked; omit
it to check feasibility alone. Zero is an accepted deadline.

Exit **0** means valid at these estimates; **2** means a well-formed plan failed
checks, with a sorted `violations` array on stdout; **1** means invalid input,
with only an error on stderr. Argparse syntax errors exit 2 without a JSON
report. Schema errors stop rather than produce partial findings.

## Bounds and limits

- 1–500 tasks; at most 500 schedule entries; ids up to 100 characters. Cycles,
  unknown prerequisites, duplicate ids/dependencies/JSON keys and unknown task
  or schedule-row fields are rejected. Completed/running snapshots and Replan's
  remaining segments are deliberately unsupported: this checks a whole job.
- Both JSON files must be ordinary files inside the current workspace, at most
  100,000 bytes each. Symlinks resolving outside the workspace are rejected.
  Concurrent filesystem changes are outside the cooperative-workspace model.
- JSON decimal spelling is checked exactly using Decimal and Fraction, with
  **no numeric tolerance**. Numeric values are limited to 100 coefficient digits
  and decimal exponent magnitude 100. Booleans and nonfinite values are invalid.
  The Python API accepts int, float or Decimal; float inputs use their `str`
  spelling. For example, `0.30000000000000004 - 0.1` does not equal `0.2` here.
  Legacy floating-point schedules can therefore be rejected; supply exact decimal
  estimates and timestamps rather than assuming a rounded approval.
- This is feasibility under supplied estimates and continuously available,
  interchangeable workers, with nonpreemptive tasks and finish-to-start edges.
  It proves neither actual execution, optimality, historical progress, worker
  skills, calendars, nor general resource availability. No task label is run.

## Checks performed

```sh
python3 -B line-1/tools/plancheck/selftest.py
```

Observed: **15 tests passed**. These include valid Workplan and Optplan outputs
(including intentional waiting), 150 seeded Workplan schedules and 150 damaged
variants, nested worker overlaps, early dependencies, missing/unknown/duplicate
tasks, exact decimals, external deadlines, invalid graphs and numbers, bounded
file reads, duplicate JSON keys, CLI exits and unchanged inputs. Test fixtures
are written only under `test/scratch/plancheck/`. Existing planner source was
read before these integrations and remains unchanged. The checker itself has
no dependency on those sibling tools; only its integration tests import them.
These are local observations, not independent certification.
