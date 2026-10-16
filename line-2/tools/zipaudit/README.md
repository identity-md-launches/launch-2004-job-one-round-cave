# ZipAudit

Check whether an extracted directory still contains exactly the bytes and paths
of an approved ZIP. This catches accidental edits, missing files, added scripts,
replaced directories and symlinks after extraction. It is read-only and never
executes archive contents. Python 3.9+ standard library only; it imports the
existing sibling `../safezip/safezip.py`, which is shipped in this repository.
No installation, network, credentials or environment variables are needed.

Run this one command from the repository root to see it work offline:

```sh
python3 -B line-2/tools/zipaudit/demo.py
```

Tried here: the demo wrapped the existing real public IMD OpenAPI capture
(`https://api.imd.fun/openapi.json`, 23,132 bytes) in a ZIP, inspected it, extracted
with that exact digest, and audited all three nodes and 23,132 bytes successfully.
It then flipped one byte in the disposable extracted copy without changing its
size: the audit rejected its content hash. The captured public data and source
metadata remain in `../safezip/imd-openapi.json` and `sample-source.json`.
This is offline replay of historical public data, not a fresh network observation.
The demo only creates disposable files under `test/scratch/` and cleans them up.

For regression checks:

```sh
python3 -B line-2/tools/zipaudit/selftest.py
```

Observed: **16 tests passed**. They cover implicit and empty directories, empty
files/archives, same-size changes, size changes, missing and unexpected files or
directories, type swaps, file/directory/root symlinks, digest approval, resource
limits, deterministic deadline expiry during traversal, invalid budgets, CLI
success/refusal and preservation of contents/modes on success and failure.
The inherited SafeZip suite also passed all **44 tests**.

## Audit your own extraction

First inspect a supplied archive with SafeZip, review its inventory and retain
its `archive_sha256`. After extraction, invoke:

```sh
python3 -B line-2/tools/zipaudit/zipaudit.py incoming.zip unpacked --sha256 APPROVED_SHA256 --seconds 10 --nodes 500
```

`APPROVED_SHA256` means the actual 64-hex digest you approved, not a shipped
value. Approval is mandatory. There is no command that derives and silently
approves the digest in this audit CLI. Python callers use
`audit(archive, tree, expected_sha256=approved_digest, seconds=10, nodes=500)`.
Success emits JSON with `ok: true`, `exact_tree: true`, archive digest, node count
and checked byte count, exiting 0. The first discrepancy, malformed archive,
invalid budget or I/O error emits `ok: false` and a reason, exiting 2. An API
caller receives `Rejected` for policy/content discrepancies; underlying I/O and
ZIP errors may propagate. Nothing is repaired or deleted.

The reference ZIP is rechecked by SafeZip, including all paths, limits, CRCs and
payload SHA-256 hashes, against the required approved digest. Implicit parents
and explicit empty directories are part of the expected tree. The audit uses
exact case-sensitive spellings and rejects every unexpected path. Directory
iteration is streamed; only expected directories are queued, so a large
unexpected subtree is refused without descending into it. Regular-file reads
are capped at expected size plus one byte; hashes catch same-size changes.
Symlinks and special filesystem objects are rejected rather than followed.

The audit forwards `--entries`, `--nodes`, `--archive-bytes`, `--file-bytes`,
`--total-bytes` and `--ratio` to SafeZip, with the same defaults and validation.
The approved tree therefore bounds traversal and file bytes. Optional `--seconds`
is one cooperative monotonic budget for reference inspection and tree checking,
not a separate new budget for each phase.

## Limits

Use a cooperative workspace with **no concurrent filesystem mutations**. Checks
and opens are separate operations: this is not a defense against local symlink
races, and a successful audit does not freeze the tree for later use. Filesystem
reads can update access times. Modes, ownership, timestamps, hard-link identity
and extended attributes are not compared. Hard links to regular files are
compared by their bytes. A positive result establishes byte/path agreement at
check time, not publisher authenticity or safety to execute. An extra file is a
failure even if harmless. This intentionally checks the whole tree, not a subset.

Both paths must stay inside the current workspace with no symlink components.
SafeZip's bounded in-memory snapshot and ZIP parser precede inventory limits;
parser overhead is not a hard RAM limit. Cooperative seconds can be exceeded by
one blocking I/O, parser, decompression or hashing call. The audit is not a CPU,
RAM, filesystem-race or hard-deadline sandbox. It needs no coin or payment.
