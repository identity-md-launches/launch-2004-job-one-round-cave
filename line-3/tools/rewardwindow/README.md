# RewardWindow

RewardWindow checks **every consecutive smallest-unit budget** in a short interval, starting at a RewardSplit request's budget. It reports each transition where increasing the total budget makes a contributor's largest-remainder allocation fall. This extends the two-budget RewardCompare review to a complete bounded window. It reuses the existing exact allocator, real historical ZTO metadata capture, and canonical receipt hashes. Python 3.9+ standard library only; no installation or network.

From the repository root, see it work:

```sh
python3 -B line-3/tools/rewardwindow/rewardwindow.py demo
```

The offline demo uses six illustrative address-free roles and scans 25 through 28 atomic ZTO units. The 25→26 transition exposes the known largest-remainder reversal: `d` and `e` each fall from 3 to 2 units while the budget rises. The output includes a recomputation receipt. Exit 0 means the scan completed, **not** that every transition was monotonic.

For your own RewardSplit request, whose `budget` is the first point:

```sh
python3 -B line-3/tools/rewardwindow/rewardwindow.py scan \
  --request REQUEST.json --steps 20 --output WINDOW.json
python3 -B line-3/tools/rewardwindow/rewardwindow.py verify \
  --request REQUEST.json --report WINDOW.json
```

Use `--metadata PATH` on both commands if the request uses a different ZTO or IMD metadata capture. `steps` is 1–128 **atomic token units**, not whole tokens; a scan from 1 ZTO with 20 steps ends at 1.000000000000000020 ZTO when decimals are 18. Every intermediate unit is computed, so no intervening reversal is inferred or skipped. Scans reaching beyond uint256 or producing a report over 256 KiB fail explicitly. Saved reports use new workspace paths and refuse overwrites; inputs are strict bounded workspace JSON. Verification recomputes the whole window against the original request and metadata and rejects altered, omitted or extra fields.

What happened here: the demo completed with exit 0, reported the 25→26 reversal, and verified the report. The self-test exercises the paradox, budget boundaries, tampering, exact conservation across seeded windows, and CLI round-tripping:

```sh
python3 -B line-3/tools/rewardwindow/selftest.py
```

This is arithmetic review. Weights, IDs and optional recipient addresses come from the caller. It does not establish work quality, entitlement, ownership, available balance, payment or authorization. The included metadata is one historical Ethereum RPC observation; hashes are unsigned. Nothing accesses keys, signs, sends, posts or pays.
