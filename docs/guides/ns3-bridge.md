# A study in ns-3 and in HandoverLab

Since 2.6.0 one study file defines a comparison with the packet-level simulator ns-3 and its 5G-LENA module:
`handoverlab ns3 export` writes a ready-to-run ns-3 package, `handoverlab ns3 import` reads the ns-3 results
back, and `handoverlab ns3 compare` runs HandoverLab on the same cells and seeds and applies the checks of the
validation studies N3 and V1 ([calibration](../calibration.md)). Without the bridge this was done by hand for
every set of ns-3 runs.

```bash
handoverlab ns3 export examples/ns3_study_v1.yaml --out v1pkg        # 1. the ns-3 package
bash v1pkg/build.sh ~/ns-3-dev && python v1pkg/run.py 6             # 2. on the ns-3 machine
handoverlab ns3 import v1pkg/V1_results.zip --out v1_ref.json        # 3. the results back
handoverlab ns3 compare examples/ns3_study_v1.yaml v1_ref.json --comparison --workers 4   # 4. checks
```

## What the bridge can run

Only what the ns-3 program `benchmarks/ns3/handoverlab-ns3-a3.cc` simulates (see
[benchmarks/ns3](https://github.com/mjs19971997/handoverlab/tree/main/benchmarks/ns3) for the program and
the ns-3 build: ns-3.48 with the listed upstream commits, 5G-LENA v5.1 with one local change):

| Study key | ns-3 program option | HandoverLab side |
|---|---|---|
| `scenario: ns3-urban-3.5ghz` (the only card) | `--scen=urban` | the [card](../scenarios/ns3-urban-3.5ghz.md) with the in-car loss of ns-3 and ideal execution |
| `rule: a3` | `--rule=a3` (stock `NrA3RsrpHandoverAlgorithm`) | `{"rule": "a3", "off_db": ..., "ttt_s": ...}` |
| `conditions.isd_m`: 200, 300, 400 | `--isd` | the site list of that distance (`handoverlab.verify.ns3`) |
| `conditions.speed_mps` | `--speed` | constant speed |
| `conditions.ttt_ms`, `conditions.offset_db` | `--ttt`, `--hyst` | `ttt_s`, `off_db` |
| `conditions.traffic`: light, mixed, full | `--traffic` (light: `--udpInterval=100`) | light: the card; full: `traffic.model: full_buffer`; mixed: export only |
| `conditions.fading`: false, true | `--fading` | true: `radio.fast_fading: tdl-c` |
| `users`, `duration_s`, `discard_s` | `--nUe`, `--simTime`, `--discard` | `mobility.users`, `run.duration_s`, `run.warmup_s` |
| `seeds` | `--rngRun` | the same seeds |
| `outputs.events`, `ctrl_csv`, `meas_csv` | `--events`, `--ctrlCsv`, `--measCsv` | (output files only; all of them go into the results zip) |

Everything else is refused with an error that names the option, before any file is written: another card
(`ns3.scenario: highway-tr37885-4ghz`), scenario changes such as beams or NTN
(`ns3.scenario: {base: ns3-urban-3.5ghz, radio: {beams: ...}}`), another rule (CHO, DAPS, LTM: 5G-LENA has
none of them), another site distance, unknown keys. The program, its options and outputs are described in its
header.

## The study file

```yaml
schema: 1
name: V1                              # starts every run tag: V1_light_d200_v10_t80_s401
description: Failure rate against fresh ns-3 runs.
ns3:
  scenario: ns3-urban-3.5ghz
  rule: a3
  users: 20
  duration_s: 180                     # simulated time in ns-3, the first discard_s excluded
  discard_s: 60
  conditions:                         # full factorial
    isd_m: [200, 300]
    speed_mps: [10, 28]
    ttt_ms: [80, 320]
    offset_db: [3]
    traffic: [light]
    fading: [false]
  seeds: {first: 401, last: 405}
  outputs: {events: true, ctrl_csv: true}
  handoverlab: {run_length: study}    # the default: the run length of ns-3
  build: {ns3_dir: ~/ns-3-dev, path: "", msys2: "C:/msys64"}
```

`handoverlab.run_length` sets the run length of the HandoverLab side: `study` (the default) runs
`duration_s` with `discard_s` as warm-up, the same as ns-3. `card` keeps the card's 150 s with 60 s warm-up;
it exists only to reproduce the registered analyses of N3 and V1, which had the wrong run length: the failure
checks compare counts, so with `card` a HandoverLab cell measures 90 s against 120 s in ns-3. Do not use
`card` for new comparisons. `build` gives the
defaults of the package scripts: the ns-3 folder, the folders put in front of `PATH` when the program runs
(on Windows the ns-3 libraries and the compiler runtime) and the MSYS2 folder.

## 1. Export

`handoverlab ns3 export STUDY --out DIR` writes:

| File | What it is |
|---|---|
| `handoverlab-ns3-a3.cc`, `COPYING` | the ns-3 program (GPL-2.0-only) |
| `build.sh` | builds the program next to itself: by default through `./ns3 build` in the ns-3 folder (`bash build.sh NS3_DIR`); with `BUILD=direct` by compiling and linking against the built ns-3 libraries (MSYS2 UCRT64 on Windows) |
| `run.py` | runs every command line of the manifest: standard library only, resumable (a run whose JSON exists is kept), several at a time (`python run.py 6`), `--dry-run` lists the command lines; at the end it zips the results into `NAME_results.zip` (the run JSONs, the event and measurement CSVs and, with `outputs.ctrl_csv`, the `_ctrl.csv` files; no logs) |
| `run.ps1` | Windows with MSYS2: builds the program if it is missing, then runs `run.py` |
| `manifest.json` | the study, its hash, the HandoverLab version, the hash of the program and every ns-3 command line |

The program is GPL-2.0-only and not part of the Python package: from a source checkout the export finds it in
`benchmarks/ns3`; with an installed package give it with `--program FILE`.

## 2. Import

`handoverlab ns3 import RESULTS.zip|DIR --out REF.json` reads the run JSONs into a reference file in the format
of `handoverlab.verify.ns3.load_reference` (one row per condition, `part: "S"`, means over the runs), with the
failure counts, the UE-minutes and one entry per run. A seed that appears twice in a condition, or a run JSON
without the fields the checks need, is an error.

## 3. Compare

`handoverlab ns3 compare STUDY REF.json` runs HandoverLab on every cell and seed of the reference (in
`--workers` processes) and reports:

| Check | Definition | Default limit |
|---|---|---|
| F1 level | sum of the HandoverLab failures over the cells / sum of the ns-3 failures | in [0.67, 1.5] (`--level`) |
| F2 order | Spearman rank correlation of the cell failure counts | at least 0.8 (`--rank-min`) |
| F3 handover rate | median over the cells of the handover-rate ratio HandoverLab / ns-3 | in [0.8, 1.25] (`--ho-ratio`) |
| F4 time-to-trigger | sign of (longest - shortest TTT) failures equal to ns-3's, in the pairs of cells that differ only in the TTT | at least 0.75 of the pairs (`--ttt-share`) |

F1 and F2 are "not measurable", and fail, when ns-3 has fewer than 20 failures in total (`--min-failures`).
The HandoverLab side has ideal execution (ns-3 has an ideal random access); `--comparison` adds the ns-3
comparison setting of 2.5.0 (`handoverlab.verify.ns3.COMPARISON_SETTING`, interferer load 0.15 at link
monitoring), a setting that brings the failure level closer (0.5-1.3 of ns-3's, depending on the
set) but is not validated: with equal run lengths it passes F1-F3 on none of the fresh sets N3, V1
and V3 ([calibration](../calibration.md)); it is not a default. `-o OUT` writes
the cells and the checks as JSON; the exit code is 0 when no check fails.

## Python

```python
from handoverlab import ns3bridge

study = ns3bridge.load_ns3_study("examples/ns3_study_v1.yaml")
man = ns3bridge.export(study, "v1pkg")                    # refuses unsupported options before writing
ref = ns3bridge.import_results("v1pkg/V1_results.zip", "v1_ref.json")
res = ns3bridge.compare(study, ref, comparison=True, workers=4)
print(res["checks"]["F1_level"], res["checks"]["pass"])
```

`compare` also takes `limits` (the keys of `ns3bridge.LIMITS`) and `overrides` (dotted scenario keys applied
to every HandoverLab cell, for calibration experiments).

## Reproduced

Exporting `examples/ns3_study_v1.yaml` gives, run by run, the same program options as the hand-made package
of study V1 (40 command lines). Importing its 40 results and running `compare` with and without
`--comparison` gives (rows C and R of V1):

| Analysis | `--comparison` (row C): level, rank, HO ratio, TTT sign | without (row R) |
|---|---|---|
| corrected, equal run lengths (`run_length: study`, the default) | 1.31, 0.62 (below 0.8), 0.92, 4 of 4 | 0.32 (fails), 0.62, 0.94, 4 of 4 |
| registered analysis, wrong run length (90 s against 120 s; `run_length: card`) | 0.97, 0.88, 0.965, 4 of 4 | 0.33 (fails), 0.84, 0.973, 4 of 4 |

The corrected numbers are the ones that count; the registered ones are reproduced exactly with
`run_length: card` and are shown only to make the correction traceable.

This difference showed that the 2.5.0 analyses of N3, V1 and V3 compared failure counts over unequal run
lengths. Redone with equal run lengths (amendment E1, registered before the corrected results were seen), the
comparison setting passes F1-F3 on none of the three sets (level 0.52, 1.31 with rank 0.62, and 0.64), so the
statement of 2.5.0 that it passed on V1 is withdrawn in 2.6.0 ([calibration](../calibration.md)). The
comparisons of handover rates were not affected.

## Limits

- The bridge does not run ns-3; build and run the package where ns-3 is installed.
- The same build, seed and command line give the same ns-3 output bit for bit; other machines or builds need
  not (benchmarks/ns3). Compare statistically, with the checks above.
- Traffic `mixed` can be exported but not compared: HandoverLab has no checked counterpart of the
  mixed ns-3 profiles.
