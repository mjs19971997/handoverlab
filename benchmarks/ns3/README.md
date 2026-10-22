# Benchmark against ns-3 / 5G-LENA

This folder holds everything needed to repeat, from scratch, the comparison of HandoverLab with the packet-level
simulator ns-3 and its 5G-LENA module (`handoverlab verify --ns3`, [calibration](../../docs/calibration.md)):

| File | What it is | Licence |
|---|---|---|
| `handoverlab-ns3-a3.cc` | the ns-3 program: Event A3 handover with the full nr protocol stack in the TR 37.885 urban grid (the scenario of the card `ns3-urban-3.5ghz`) | GPL-2.0-only, like ns-3 (`COPYING`) |
| `run_benchmark.py` | runs parts A, B and C of the reference and writes `reference.json` in the format of the stored reference | MIT |
| `COPYING` | the GNU General Public License version 2 | |

The rest of HandoverLab is MIT-licensed; the GPL applies to the ns-3 program only, which is not part of the Python
package.

## 1. Build ns-3 as for the reference runs

| Part | Version |
|---|---|
| ns-3 | tag `ns-3.48`, plus the upstream ns-3-dev commits `b5520504a` and `ae5529988` (MR 2883), `fa33c33cf` (MR 2929) and, on Windows, `2beb9d9a6` |
| 5G-LENA | `contrib/nr` at tag `v5.1`, with one local change: in `NrSpectrumPhy::StartRxSrs` (`contrib/nr/model/nr-spectrum-phy.cc`) the five `NS_FATAL_ERROR` calls replaced by `NS_LOG_WARN`, so that an uplink SRS that reaches a busy receiver after a handover is dropped instead of aborting the run |
| Build | `./ns3 configure -d optimized --enable-modules=nr`, then `./ns3 build`; the reference used g++ 16 (MSYS2 UCRT64 on Windows) |

Copy `handoverlab-ns3-a3.cc` into `scratch/` and build again (`./ns3 build`). The program prints its options with
`--help`; its header lists them with their defaults and describes every output file.

## 2. Run the reference parts

```bash
python run_benchmark.py --exe build/scratch/ns3.48-handoverlab-ns3-a3-optimized --parts A --workers 6
```

| Part | Runs | Length | Simulated time per run, wall time on one core (reference machine) |
|---|---|---|---|
| A: 24 settings x 4 conditions | 96 | 150 s, the first 60 s discarded | about 16 minutes |
| B: 2 settings x 6 conditions x `--runs-b` (20) | 240 | 180 s | about 19 minutes |
| C: one setting, 20 cells x `--runs-c` (10) | 200 | 180 s (two cells 600 s) | 20-60 minutes |

Finished runs are kept in `results/runs/`; running the script again runs only what is missing. On Windows give the
library folders with `--path "C:/ns-3-dev/build/lib;C:/msys64/ucrt64/bin"`. `--dry-run` lists the runs.

## 3. Compare

```bash
handoverlab verify --ns3 --ns3-reference results/reference.json --ns3-seeds 3
```

runs HandoverLab on the same 24 settings and four conditions and applies the limits fixed in version 0.2 (median
ratio of the handover and unnecessary-handover rates in [0.8, 1.25], rank correlation at least 0.9); failure rates
and SINR are reported without a limit. `handoverlab.verify.ns3.holdout(reference=...)` compares parts B and C.

## What to expect

- The same build, seed and command line give the same output bit for bit. Different machines or builds need
  not: one run of part A gave 5.63 handovers per UE-minute on one machine and 6.47 on another with the same
  command line. Under load the results of nr v5.1 even depend on the heap layout of the process. Compare the
  benchmark statistically (the limits above), not run by run.
- Two reruns with this program on other machines, compared with the stored results:
  - part A (96 cells, one run each; an 8-core Windows Server, nr v5.1): 89 cells identical to the stored
    ones, the 7 others all at 400 m ISD and mostly 30 m/s with long time-to-trigger, within 0.87-1.13 of the
    stored handover rate (median ratio over all cells 1.000 for handovers, unnecessary handovers and
    failures);
  - parts B and C (32 cells, 10-20 runs each; an Intel Core i9 desktop): median ratio 1.000, rank
    correlation of the cells 1.00 / 1.00 / 0.99 (handovers / unnecessary / failures), and every cell within
    two standard errors of the stored mean (|z| < 2 in 32 of 32).
  See `docs/calibration.md` for the comparison with HandoverLab and for why the absolute failure rates of
  the two simulators differ.
