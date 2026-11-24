# CarbonLatch

[Stable Studionet contract](https://explorer-studio.genlayer.com/address/0x70Be1D36361c6edf8Ee8A4051c35F5ae196c61b4) · [Deployment transaction](https://explorer-studio.genlayer.com/tx/0x5c663b37abb7b5cd31375deb3f80cd9446e23277d84a903f70a8ac3bd472b8e7)

A replayable dispatch signal for discretionary electric workloads using Great
Britain’s published half-hour carbon intensity. An operator deploys a stream
with a UTC start and two integer thresholds in gCO₂/kWh. Consumers use the
latest checkpoint to reconstruct the schedule. Each slot is processed once,
in order, and each checkpoint records its actual intensity and dispatch mode.

For each call, validators fetch the [Carbon Intensity archive](https://carbonintensity.org.uk/)
and agree on the exact ordered actual-value vector. The query may return
extra rows at its boundary. Only the requested half-hours are used. Missing,
duplicate, or invalid actuals fail the whole batch. Forecasts are excluded.
Code switches to ALLOW at or below the lower threshold and to HOLD at or
above the upper threshold. Between thresholds, the previous mode persists.

| Call | Result |
| --- | --- |
| `advance(expected, sections)` | Anyone may commit one to six contiguous half-hours starting at the current cursor. |
| `checkpoint(start)` | Read the finalized result for one completed half-hour or an empty string. |
| `state()` | Read the cursor and current mode. The initial mode is HOLD. |

Archive corrections do not rewrite settled checkpoints. An absent interval
blocks advancement until the source supplies an actual value. The published
national series is an estimate. The contract provides an auditable historical
signal and does not control equipment or predict future grid intensity.

The [example](scenario.json) calibrates the thresholds to 64 and 70. It
processes three audited historical half-hours and attempts to reuse the old cursor.

## Build and verify

Use Node.js 24 and Stable Studionet (chain ID 61999).

```sh
npm ci
python3 -B -m unittest discover -s tests -v
python3 -m pip install genvm-linter==0.11.0
genvm-lint check contracts/contract.py --json
npm run verify:live
```

The Python suite uses an in-memory SDK stub. The
[official lint result](evidence/genvm-lint.json) validates the declared SDK.
The [chain evidence](evidence/studionet.json) is independently checked by the
read-only verification command. It compares deployed source bytes, receipt
execution and finalized state.

In a separate working copy, `STUDIONET_FAUCET=1 npm run deploy` deploys a fresh
instance and exercises the exact calls in the scenario using a test wallet.
