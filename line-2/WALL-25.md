# Wall 25 — The Returning Feather

A feather returns beside two stones: compare what remains with what was carried.
ZipAudit similarly checks an extracted tree against the approved archive,
including every implicit parent directory, empty directory and file hash.

The built-in imagegen tool added the feather and paired stones to bare rock
below the basket. `finish-wall-25.cjs` reused the existing line-1 PNG/JPEG codec
without changing it. Only x=500–750, y=850–980 was blended with eight-pixel edges.
The finished wall retains all 1,540,395 protected pixels exactly; 31,913 pixels
changed inside the patch. All ancestral pigments lie outside it. The PNG
encode/decode round trip is lossless. See `media-check-25.json` for measurements.

- Required output: `artifacts/line-2/wall-v6.png`, RGB PNG, 1254 × 1254.
- Continuation: `artifacts/line-2/wall.png`, identical bytes.
- Preview: `dist/line-2/25.jpg`, JPEG, 512 × 512, 88,759 bytes.
- New record: `dist/line-2/25.json`; all 24 older records remain unchanged.
- PNG SHA-256: `be0c3c3cd5b3fad1408455efbe39e4a3dd81776d3fc3760655909c83c7a7ed98`.

Inspected both final images. The inherited frog remains Pepe, with a wide mouth
and large heavy-lidded eyes. Counted five digits on each inherited hand (four
fingers and a thumb). No new hands or handprints. The feather is irregular,
earth-colored and worn, with rock showing through. No letters, numbers, captions,
signatures, logos, watermarks, borders, real people or prohibited symbols were
observed. No unmet visual requirement was observed. This is a local visual
assessment, not independent approval. Rock within the small additive patch is
generatively reconstructed; preservation outside it is checked numerically.

The specifically requested JPEG is beside its record, as in earlier rounds;
this follows the explicit FILES requirement despite the conflicting general
images-only-under-artifacts sentence. No draft or crop was saved. The named
output is left untracked/ignored for the upload daemon, with no force-add.

Working demonstration:

```sh
python3 -B line-2/tools/zipaudit/demo.py
```

The public IMD capture audited exactly (three nodes, 23,132 bytes), then a
same-size byte flip was refused. ZipAudit's 16 tests and SafeZip's 44 tests passed.
The new tool and demo need only Python's standard library and the unchanged
sibling SafeZip. Its README explains cooperative filesystem/time boundaries,
mandatory byte approval and the distinction between agreement and trust.
