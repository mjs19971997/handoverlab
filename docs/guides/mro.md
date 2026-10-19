# How to compare a rule with A3 tuned by MRO

In a real network the handover parameters are not left at one fixed value: mobility robustness
optimisation (MRO), a self-organising-network function (TS 38.300 clause 15.5.2; TS 28.313;
the SON concepts of TS 32.500), tunes them from the observed outcomes of handovers. A new rule
should therefore be compared not only with fixed A3, but also with A3 under MRO. Since 1.7.0 the
rule `a3_mro` provides that baseline.

## 1. What `a3_mro` does

- **Trigger.** Event A3 (TS 38.331 clause 5.5.4.4) with `off_db` and a fixed `ttt_s`, plus a cell
  individual offset (CIO) for every pair of serving and neighbour cell, which starts at 0 dB.
  A positive CIO delays the handover of that pair.
- **Counting.** Within each window of `window_s` seconds the rule counts, per pair, the failure
  classes of TS 38.300 clause 15.5.2. *Too late*: a late handover, and a link failure without a
  handover after which the UE re-establishes in a neighbour (counted for that pair). *Too early*:
  a too-early or a wrong-cell handover. *Ping-pong*: a return to the previous cell within
  `pingpong_s` (default `protocol.pingpong_s`, 1 s), which the rule sees in the serving cell of the
  user, as a network sees it in the cell history of the UE; it counts as too early for the pair of
  the first handover. Useful handovers are not counted. The wider HandoverLab label *unnecessary*
  (a short stay or a low gain) is not an MRO counter and is left out unless `count_unnecessary` is
  set.
- **Update.** At the first measurement instant at or after the end of a window, every pair with at
  least `min_events` counted outcomes moves its CIO by `step_db`: down (earlier) if too-late
  outcomes are in the majority, up (later) if too-early ones are, not at all on a tie. The CIO stays
  within `[min_db, max_db]`, and all counts restart. The rule draws no random numbers.

With `step_db: 0` it is `a3` with `off_db` and `ttt_s`; the test suite checks that both give the
same event log. The time-to-trigger is not tuned. The CIOs are kept per run, so each run starts
from 0 dB and needs time to adapt: use a warm-up (`run.warmup_s`) that covers several windows.

| Parameter | Default | Meaning |
|---|---|---|
| `off_db` | 3.0 | A3 offset before any tuning [dB] |
| `ttt_s` | 0.16 | time-to-trigger [s] |
| `step_db` | 0.5 | change of a pair's CIO per window [dB] |
| `window_s` | 10.0 | length of a counting window [s] |
| `min_db`, `max_db` | -4.0, 4.0 | bounds of a CIO [dB] (TS 38.331 allows -24 to 24 dB) |
| `min_events` | 1 | counted outcomes a pair needs in a window before its CIO moves |
| `count_pingpong` | true | count a return to the previous cell within `pingpong_s` as too early |
| `pingpong_s` | none | ping-pong time [s]; none: `protocol.pingpong_s` |
| `count_unnecessary` | false | also count every unnecessary handover as too early (a ping-pong then counts twice) |

## 2. Run it next to fixed A3

```yaml
schema: 1
scenario:
  base: urban-grid-10ghz
  mobility: {users: 30, profile: veh30}
  radio: {isolation: 1.0}
  run: {duration_s: 300.0, warmup_s: 60.0}
seeds: [1, 2, 3]
rules:
  - {rule: a3, name: A3-6dB, off_db: 6.0}
  - {rule: a3_mro, name: MRO-6dB, off_db: 6.0}
  - {rule: a3_mro, name: MRO-6dB-fast, off_db: 6.0, window_s: 5.0, step_db: 1.0, min_db: -6.0}
  - {rule: a3, name: A3-3dB}
  - {rule: a3_mro, name: MRO-3dB}
output: results/mro.csv
```

Means over the three seeds, per user-minute:

| Rule | Failures | Too late | Too early | Ping-pong | Unnecessary | Interruption [s] |
|---|---|---|---|---|---|---|
| A3-6dB | 0.431 | 0.289 | 0.028 | 0.025 | 0.642 | 1.167 |
| MRO-6dB | 0.308 | 0.203 | 0.031 | 0.017 | 0.625 | 1.048 |
| MRO-6dB-fast | 0.264 | 0.183 | 0.033 | 0.014 | 0.592 | 1.003 |
| A3-3dB | 0.303 | 0.111 | 0.033 | 0.114 | 1.075 | 1.061 |
| MRO-3dB | 0.233 | 0.094 | 0.028 | 0.075 | 0.956 | 0.986 |

Starting from an offset that is too large (6 dB), MRO cuts the failures by about 30 % (40 % with
the faster setting) through fewer too-late handovers. Starting from 3 dB, it cuts failures by
about 20 % and ping-pong by about a third. Three seeds are few: read a comparison like this with
the paired statistics of a study (`handoverlab study`), not from the means alone.

## 3. Use it as a baseline

In a [tuning study](../tutorials/tuning-study.md), `a3_mro` can be one of the compared methods
next to your own rule. It is a plain counter-based MRO, not a product algorithm: vendors combine
more counters, per-cell and per-pair parameters, and time constants of hours or days. State this
when you report a comparison with it.
