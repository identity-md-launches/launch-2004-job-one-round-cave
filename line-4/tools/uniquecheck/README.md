# UniqueCheck

Find potential breaking changes to array uniqueness in OpenAPI 3.0.x and 3.1.x JSON descriptions. Python 3.9+ and only the standard library; no installation. Keep the sibling ApiDelta, BoundCheck, MultipleCheck and ConstCheck folders together.

From the repository root, see it work with one command:

```sh
python3 -B line-4/tools/uniquecheck/uniquecheck.py demo
```

The offline demo uses the bundled real public IMD API description. In memory, it adds an illustrative optional `clientTags25` array, then makes its elements unique. It reports **one potential breaking finding and one retained review finding** over five operations. The illustrative old value `["urgent", "urgent"]` explains the rejection. This is a hypothetical change, not a claim that the service changed. Successful demonstrations exit 0.

Compare local JSON descriptions:

```sh
python3 -B line-4/tools/uniquecheck/uniquecheck.py compare old.json new.json
```

Input paths must resolve inside the current workspace. Output is deterministic JSON on stdout, including exact input-byte SHA-256 hashes and locations. Exit 0 means no detected breakage, 1 potential breakage, 2 invalid input/processing failure, and 3 unresolved review only. Accept only exit 0 as an automated pass within the documented scope; it is not a proof of compatibility.

Requests must keep accepting old arrays: adding `uniqueItems: true` can reject repeated values that old clients sent. Responses must keep meeting old guarantees: removing `true`, or replacing it with `false`, can admit duplicates that old consumers excluded. Missing `uniqueItems` means false. Explicit values must be JSON booleans when visited. If both schemas explicitly exclude arrays by their types, no uniqueness breaking finding is added. Type changes still receive inherited analysis. The rule works in both supported OpenAPI versions, unlike the inherited 3.1-only `const` rule.

All earlier findings remain, including generic review for changed uniqueness constraints. A relaxation or equivalent explicit false can therefore still require review. Arrays limited to one element, enums, fixed values, impossible schemas and compositions can make duplicate values unreachable; this rule does not prove such satisfiability, so its findings are potential breaks. It does not implement a JSON Schema validator or compare actual API responses. Changed compositions, boolean schemas and unsupported schema dialects retain the earlier tools' limitations and reviews. No compatibility guarantee follows from zero findings.

The inherited loader caps descriptions at 1 MiB, 50,000 nodes and depth 80; analysis caps visits at 20,000 and findings at 2,000. Local references only; no remote references are fetched. Unchanged schemas and unused constraints can bypass validation, so this is not a full OpenAPI validator. Numeric rules inherit float parsing limitations. No API operation, configuration, account, environment variable, key or wallet is accessed by the tool.

## Tried on 2026-10-16

- `python3 -B line-4/tools/uniquecheck/selftest.py`: **10 tests passed**, including 36 request/response/version cases against independently enumerated accepted arrays, default/false equivalence, unions, non-array types, invalid booleans, nested arrays, recursive local references, escaped locations, earlier findings, exact-input hashes and all four CLI exits.
- All **82 inherited tests** passed unchanged: ApiDelta 44, BoundCheck 11, MultipleCheck 16, ConstCheck 11.
- Demo: five operations, one breaking finding, one retained review finding, exit 0.
- A read-only GET of `https://api.imd.fun/openapi.json` with User-Agent `Pepeolithic-UniqueCheck/25.0` returned HTTP 200 and 23,132 bytes. SHA-256 matched the bundled capture (`be142840c010710cb2a5b9e5c73e71d8e79ec4054c15661699d60bfa627be96a`); comparison found five operations and no findings. See `line-4/live-check-25.json`. Only the public description was fetched, and no described operation was executed.

Static compatibility checking needs no coin, balance or payment; ZTO and IMD are not needed for this piece.
