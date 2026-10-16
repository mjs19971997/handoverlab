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
