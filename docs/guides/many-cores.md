# How to run on many cores

A single run uses one core: the step loop is sequential and the radio arrays are too small for
multi-threaded BLAS to help. Parallelism therefore comes from running many worlds (conditions and
seeds) at once.

## Studies: `--workers`

A [study](../tutorials/tuning-study.md) splits into jobs (one world with its rules) and runs them
in worker processes:

```bash
handoverlab study my-study.yaml --dry-run          # jobs per stage, rule runs, nothing is run
handoverlab study my-study.yaml --workers 16
```

- Each worker is one process with BLAS and OpenMP limited to one thread, so `--workers N` uses
  about N cores. Without `--workers` HandoverLab leaves cores free: the logical CPUs minus four
  (half of them on machines with fewer than eight). `workers: N` in the study file sets a default.
- Memory grows with the workers: every worker builds its own world. The job records list the peak
  memory of each job (`jobs/<stage>/<job>.json`); keep N times that below the free memory.
- Neither the worker count nor the order of the jobs changes a result: the fingerprints of the
  event logs are the same with 1 or 64 workers.
- Jobs start longest first, so the last minutes are not spent on one large job alone.

## Variants that differ only in engine settings: one radio stream

In runs with beams, angular spread or blockage most of the time goes into the radio samples, not
into the protocol engine. Variants that differ only in settings that the engine alone reads (the
SS-SINR definition `radio.beams.ssb_sinr`, beam failure detection `radio.beams.bfd`, the
`protocol` timers, filters and measurement periods, ...) have the same world and the same radio
samples on a seed. Since 2.11.0 they can run on one radio stream: each variant still gets its own
world and engine, and its results are those of a separate run, bit for bit; the radio samples are
only computed once.

In a study, `--share-radio` runs the jobs of one seed whose conditions differ only in such
settings in one worker:

```bash
handoverlab study my-study.yaml --workers 6 --share-radio
```

The job records are the same as without the flag (job IDs, fingerprints, metrics, event logs);
a shared job's record has `radio_shared` (the number of jobs that used the samples), and its
`timing.radio_s` is the time of the shared samples. A shared task holds the worlds of all its jobs
at once, so it needs more memory than a single job, and it occupies one worker for longer.

In Python, `simulate_variants` groups a list of scenarios the same way, and `run_shared` runs
worlds you built yourself:

```python
import handoverlab as hl

base = hl.builtin_scenario("urban-macro-tr37885-4ghz").with_overrides(
    {"radio.beams": {"sectors": 3, "n_ssb": 8, "panel": [8, 8], "angular_spread": "tr38901"}})
variants = [base,
            base.with_overrides({"radio.beams.ssb_sinr": "ssb"}),
            base.with_overrides({"radio.beams.bfd": False})]
per_variant = hl.simulate_variants(variants, [{"rule": "a3", "off_db": 3.0, "ttt_s": 0.256}], seeds=[1, 2, 3])
# per_variant[i] equals hl.simulate(variants[i], ...); the three share one radio stream per seed
```

Which variants may share is decided by `hl.radio_key(scenario)`: the hash of the whole scenario
without its name, without the `protocol` keys other than `step_s` and `l1_period_s`, and without
the beam keys that only the engine reads (`report_s`, `switch_db`, `tci_delay_s`, `rx_sweep_n`,
`bfd`, `bfi_max`, `bfd_timer`, `bfr_timer_s`, `rsrp_thresh_ssb_dbm`, `ra_attempt_s`,
`preamble_max`, `rlm_rs`, `ssb_sinr`, `ssb_overlap`). Variants with the same key share; any other
difference, even one that would leave the radio samples unchanged (the traffic, the duration,
`run.backend`), keeps them apart. A test reads the code of the world and of the radio sources and
fails if it ever reads one of these engine-only keys.

## Long studies on a server

A study can be stopped at any time and continued, with the same or another worker count; finished
jobs are kept and never run again:

```bash
nohup handoverlab study my-study.yaml --workers 32 -q > study.log 2>&1 &
handoverlab status results/my-study                # finished, failed and remaining jobs, time left
# ... stopped, rebooted, or moved to another machine with the directory ...
handoverlab study my-study.yaml --workers 32       # continues where it stopped
handoverlab report results/my-study
```

A failed job leaves its traceback in `failed/<job>.txt` and stops the study after its stage; the
next run retries it. `handoverlab status` estimates the time left from the study's own finished
jobs; on a shared machine it is a lower bound.

Several machines can share the work only through the study directory: run the stages one after the
other, or copy the finished `jobs/` records into one directory and run `handoverlab study` there
again, which then only plans what is missing.

## Experiments and your own scripts

`handoverlab run` runs its seeds one after the other. For many seeds, split them over processes
and merge the CSV files (the rows are independent):

```bash
for s in 1 2 3 4 5 6 7 8; do
  handoverlab run exp.yaml --seeds $s -o results/exp-$s.csv -q &
done; wait
```

In Python, run one world per process, for example with `concurrent.futures`:

```python
from concurrent.futures import ProcessPoolExecutor
import handoverlab as hl

RULES = [{"rule": "a3"}, {"rule": "cho"}]

def one(seed):
    sc = hl.builtin_scenario("urban-grid-10ghz")
    return hl.simulate(sc, RULES, seeds=[seed])

if __name__ == "__main__":
    with ProcessPoolExecutor(max_workers=8) as ex:
        results = [r for rs in ex.map(one, range(1, 33)) for r in rs]
```

Set `OMP_NUM_THREADS=1` (and `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`) before starting such a
script, so that the processes do not compete for cores; `--workers` does this for you.
