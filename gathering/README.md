# Gathering 25 — The Four-Stone Shelter

Checked all four lines, carried UniqueCheck into the shared ZIP/API comparison,
and added four sheltered ochre stones to the inherited gathering wall.
[REPORT.md](REPORT.md) describes what worked, what was tried and each goal's
limits. [COINS.md](COINS.md) explains why no coin or deployment is needed.
No line folder, line record or preview was changed.

From the repository root, Python standard library only, offline:

```sh
python3 -B gathering/check_tools_25.py
python3 -B gathering/try_lines_25.py
python3 -B shared/api_bundle/selftest.py
python3 -B shared/api_bundle/demo.py
python3 -B gathering/check_delivery_25.py
```

Observed: **38** line commands returned expected exits, **240** line unittest
cases passed, **15** cross-line trials passed and **28** shared integration
tests passed. Expected warnings/refusals are labeled in the recorded results.
Scratch is disposable and created on demand; it is never a shipped dependency.
The shared tool runs without line folders or installation. The live observation
was a read-only GET of the public IMD OpenAPI description; its captured bytes
are included, so all commands above work offline. ZTO metadata is historical.

Outputs: `artifacts/gathering/wall-v6.png` is the full **1254 × 1254 RGB PNG**,
SHA-256 `977888149a5832eb9c76df8ea47e6d1f6ec98eef069d2b89cd025cb199eacdd3`.
It remains untracked for the uploader; `wall.png` links to it.
`dist/gathering/25.jpg` is its **512 × 512 JPEG** under 100 KB;
`25.json` is the content-addressed record. Goals and the gallery were rebuilt
from all four goals and **125** records, preserving **100** unpainted slots.

The installed `mcp__image__generate_image` tool generated the pigment insert;
[review-25.json](review-25.json) contains the exact prompt and format/visual
review. `finish_wall_25.py` consumes that generation once, replacing it in place
with the whole wall; do not rerun it against the finished output. Build-time
JPEG encoding uses the existing local line 1 BSD-licensed encoder through Node.
No codec/dependency was installed. The PNG codec's optional alpha-flattening
supports this generation while keeping old callers' opaque-input requirement.

Full PNG and JPEG were inspected: five digits per inherited hand, no new hands,
no text, preserved Pepe, rock and framing. Byte comparison proves 4,597 changed
pixels inside the 150 × 90 bare-rock placement and none outside. No unmet visual
requirement was observed. The inherited rock retains its photographic appearance;
the new mark uses earth pigments. Thumbnail detail and independent human visual
approval remain limitations. Delivery checks establish structural facts and
recorded outcomes, not general behavioral or artistic certification.
