# Performance

This page records where the time of a run goes and what was changed to make it shorter. Every
change keeps the results bit-identical: the regression tests against the bh6 prototype (36 runs,
every metric and every event log of the wide sample) and the golden event-log fingerprints pass
unchanged, and the radio maps, trajectories and event logs of four test worlds (3 x 3 grid,
2 x 2 grid with UMa and partly moving shadowing, 2 x 2 grid without clutter at 3.5 GHz, open area)
were compared array by array before and after each change.

## Reference job

Default scenario (`urban-grid-10ghz`: 3 x 3-block grid, 76 sites, 0.2 million street pixels at 1 m),
40 users, 60 s, rules A3 and CHO, one process on a modest virtual machine (Python 3.12, NumPy 2.4).

| Part | 0.1.0a1 | 0.2.0a1 |
|---|---|---|
| World (radio map, trajectories, services) | 25.2 s | 16.7 s |
| Radio samples for the run | 3.4 s | 3.2 s |
| Engine A3 / CHO | 3.9 s / 5.2 s | 4.1 s / 5.6 s |

The world is built once per seed and shared by all rules of that seed; the engines grow with the
simulated time and the number of rules. Timings on a virtual machine vary by about 10 %.

## Profile of 0.2.0a1 (largest items)

World build (16.8 s in the profiler):

| Item | Time | Note |
|---|---|---|
| line of sight to the buildings (`layout.los_matrix`) | 4.2 s | slab test per site and building |
| Gaussian smoothing of the random fields (SciPy `correlate1d`, 306 passes) | 3.5 s | 153 fields of 0.26 million pixels |
| radio map assembly (`RadioMap.__init__` itself) | 2.4 s | distances, casts, LOS state |
| path loss of 15 million links (`path_loss`) | 1.9 s | |
| random numbers and normalisation of the fields | 1.0 s | |
| bilinear interpolation of the fields | 1.1 s | |

Engines (11.5 s for both rules over 6,000 steps): the step loop (`Engine.advance`, 3.3 s own time)
and the measurement instants (`Engine._measure`, 2.6 s own time, 7.2 s with the procedures) dominate;
the work is NumPy calls on small arrays, so the time is mostly call overhead.

## Changes in 0.2.0a1

- **Path loss** computes the logarithm of the 3-D distance once for the LOS and NLOS formulas, the
  second breakpoint branch only where it applies, and the rest in place.
- **Spatially consistent LOS state** is evaluated only for links that the buildings leave clear
  (the others are NLOS anyway): the random field is interpolated and the inverse normal
  distribution evaluated for about an eighth of the links.
- **Random fields** are generated plane by plane in contiguous memory and transposed once, instead
  of being written into a strided array; interpolation gathers rows of a flat array and works in
  place, keeping the order of every product and sum.
- **Line of sight** computes the side tests of all points against every building once and tests
  the buildings nearest to a site first (the result does not depend on the order).
- **Engine**: the interference sum of a step is reused at the measurement instant instead of being
  recomputed.

Together these shorten the world build by about a third. The engine time is unchanged within the
measurement noise; it now also computes the event-log fingerprint of every run, which costs little.

## Changes in 0.3.0a1: batched engines

A study job runs many rules on one world: the tuning jobs of a study run the reference rule and every
setting of every tuned method together (11 rules in the first tuning round of
`examples/study_smoke.yaml`, often more). The profile of 0.2.0a1 showed that the engines spend
their time in NumPy calls on small arrays, once per rule and step. Version 0.3.0a1 takes the first
three steps of the performance plan:

1. **Per-step work only where it changes.** The interference weight of the serving cells changes
   only at measurement instants (load update) and when a user changes cell, so it is gathered only
   then; a baseline handover procedure counts its pending commands instead of searching for them
   every step.
2. **Batched engines.** `EngineBatch` stacks the per-user state of the radio-link monitoring
   (serving cell, connection state, timers, Qout / Qin filters, T310) and the cell load of all K
   engines of a world into arrays of shape (K, U) and (K, M). Each engine keeps views of its own
   row, so all event handling (executions, failures, procedures, outcome labels) runs unchanged.
   Per step one set of array operations serves every rule: serving SINR, Qout / Qin filters, N310 /
   T310, the expiry of T310 and the ends of executions. At measurement instants the rules decide one
   by one (their procedures differ), and then the load and scheduling model runs once for all
   engines. Only the interference sum of each engine (a matrix-vector product), the logarithms of
   the rate model and the sums of the accumulators stay per engine, on arrays laid out exactly as in
   a single engine.
3. **Compiled kernels: not added.** They would need Numba or a compiled extension. After batching,
   the remaining time is spread over the decisions of the rules at measurement instants, which a
   kernel of the step loop does not reach; an optional kernel is kept on the list for a later
   version, behind a switch and with the NumPy path as the reference.

Element-wise operations give the same result whatever the array shape, but NumPy's vectorised
logarithms can differ in the last bit between array layouts; they are therefore evaluated per engine
on arrays of the same layout as before. Results are bit-identical: the batched and the one-by-one
engines give identical event logs and metrics (`verify` group `invariants`, `tests/test_batch.py`),
the golden fingerprints and the bh6 regression (every metric to the last bit) are unchanged.
`run_world(..., batch=False)` runs the engines one by one; engines in debug mode always do.

Engine time (without the radio samples) on the stressed `smoke` scenario (20 users, 30 s, no beam
isolation), K rules on one world, one process:

| Rules per world | One by one | Batched | Ratio |
|---|---|---|---|
| 2 | 4.2 s | 3.8 s | 0.90 |
| 4 | 8.1 s | 6.0 s | 0.74 |
| 8 | 16.9 s | 9.7 s | 0.57 |
| 24 | 50.7 s | 25.0 s | 0.49 |
| Reference job (2 rules, 40 users, 76 cells, 60 s) | 9.3 s | 9.5 s | 1.02 |

With two rules the gain is within the measurement noise; with many rules per world, as in tuning,
the engines need about half the time. The world build is unchanged (about 17 s for the reference
job). Studies also gain from reuse: a rule run that is already stored (the reference rule, a setting
that two budgets select) is not simulated again, and from worker processes (one job per process).
For example, the ns-3 reference case with both load variants of the validation section (8 jobs of
24 rules x 150 s) took 1 min 53 s with four workers.

## Changes in 1.11.0: an optional compiled kernel

`run.backend: numba` (`pip install handoverlab[fast]`) runs the element-wise work of every step in
one compiled loop (`handoverlab.engine._kernels`): the serving SINR, the Qout / Qin filters and the
start, stop and expiry of T310, for N310 = N311 = 1 without the monitoring-load option. The
interference sums (matrix products) and the logarithms stay in NumPy, because a loop does not
reproduce their summation order and vectorised functions bit for bit. Each value is computed with
the same operations in the same order as in NumPy, without fast-math, so the event logs are
identical: all 30 golden runs give the same fingerprints with both backends (`tests/test_v111.py`
checks four of them whenever Numba is installed). The NumPy path stays the reference and the default;
other settings, debug mode and the engine of the beam and carrier options use it.

Engine time (median of three runs after the kernel is compiled; Numba 0.68, NumPy 2.4, one process
on the same modest virtual machine):

| Job | NumPy | Numba | Ratio |
|---|---|---|---|
| Reference job (2 rules, 40 users, 76 cells, 60 s), batched | 15.3 s | 10.0 s | 0.66 |
| Reference job, one engine at a time | 12.1 s | 10.3 s | 0.85 |
| Stressed `smoke`, 8 rules on one world, batched | 7.9 s | 7.1 s | 0.90 |

The gain is 10-34 %, not the factor of two to three hoped for in the plan: after batching, most of
the remaining time is spent in the rules' decisions at measurement instants, in the load model and
in the matrix products, which the kernel does not touch. Timings on this machine vary by 10-20 %
between runs (the NumPy batched and one-by-one times above are in the opposite order of the 0.3.0a1
table), so read the ratios as approximate.

## Changes in 2.4.0: a compiled slot scheduler

The slot scheduler of 2.2.0 (`protocol.scheduler`) plays every slot of a measurement interval in
Python on arrays as small as the number of users; a profile of the ns-3 card (10 users, 6 s) put
90-97 % of a run in that loop (2-5 ms of interpreter overhead per 0.5 ms slot). With
`run.backend: numba` the slots now run in one compiled loop (`handoverlab.engine._kernels.sched_slots`).
What needs a logarithm, an interpolation or the normal tail of the block-error model stays in the
NumPy functions of the reference: per interval they fill tables of MCS, TBS and block error
probability per user and PRB count, and of the block error probability of every later HARQ
transmission (its combined SINR is a fixed sequence of additions of the user's SINR, which is
constant within the interval). When the loop needs an entry that is not there yet (round robin with
a new PRB share), it stops before changing anything in that slot and continues once the entry is
filled. The loop itself does only basic arithmetic in the reference order, without fast-math, so
the results are bit-identical: `tests/test_sched_kernel.py` compares delivered data, PRB shares,
HARQ state and PF averages over random intervals and fingerprint and every metric of whole runs
(round robin, proportional fair, fast fading, buffers) with `==`.

Engine time on the ns-3 card (`full_buffer`, 6 s with 1 s warm-up, seed 1, rule a3; world built
once, median of three runs after the kernel is compiled; Numba 0.68, NumPy 2.4, SciPy 1.18, one
process on the same modest virtual machine, which other jobs shared at the time):

| Case | NumPy | Numba | Ratio |
|---|---|---|---|
| Rate model (no scheduler), 10 users | 1.01 s | 0.38 s | 2.7 |
| `pf`, 10 users | 60.0 s | 1.01 s | 59 |
| `rr`, 10 users | 58.7 s | 1.19 s | 49 |
| Rate model, 30 users | 0.93 s | 0.60 s | 1.5 |
| `pf`, 30 users | 69.3 s | 1.69 s | 41 |
| `rr`, 30 users | 77.1 s | 3.30 s | 23 |

In this table a scheduler run with Numba costs about 2.7-3.1 times the rate model with Numba with
10 users and 2.8-5.5 times with 30 users; with NumPy it costs 58-83 times the rate model with NumPy.
An earlier measurement on a less loaded machine, before the MCS look-up was vectorised
(`SlotScheduler.select_all`, same values as `select`), gave ratios of 10.9-23 with 10 users; the load
of the machine changes the NumPy times by up to a factor of two, so read the ratios as approximate.

Measured again for 2.4.2 on the configuration of the [scheduler picture](guides/scheduler.md)
(`tools/make_scheduler_figure.py`: the ns-3 card, 10 users, `full_buffer`, 20 s without warm-up,
seed 1, rule a3; the world build is not timed, one run per case after the kernel is compiled; Numba 0.68,
NumPy 2.4, SciPy 1.18, the same machine):

| Case | NumPy | Numba | Ratio |
|---|---|---|---|
| Rate model (no scheduler), median of three | 1.02 s | 0.58 s | 1.8 |
| `rr` | 92.7 s | 2.2 s | 42 |
| `pf` | 93.3 s | 1.0 s | 93 |

With NumPy a scheduler run costs about 91 times the rate model; with Numba 1.0-2.2 times the rate
model with NumPy (1.7-3.8 times the rate model with Numba). The remaining time is mostly the MCS look-ups and block error
probabilities in NumPy (per interval) and, for `rr`, the stops of the loop at new PRB shares.

Fast fading and the user-plane buffers were profiled too and left as they are: the fading step is
one BLAS matrix product per step (already compiled; a loop would not reproduce its summation
order), and the buffers take well under a second per run.

## Changes in 2.10.1: blockage model A in blocks

A profile of the 2.10.0 real-data runs put 91 % of the radio time of the FR2 card with `radio.blockage: a` in
`BlockageA.factor_db`, which held about eleven float64 arrays of (instants x users x sites x 16 nodes x 4 blockers)
at once, 156 MB each for one chunk (100 L1 instants, 40 users, 76 sites): a process needed about 2.1 GB, and seven
such runs in parallel did not fit in 16 GB. It also evaluated both LOS states for every link, although a link of
the street grid is either LOS or NLOS (2 % of the links are LOS). Version 2.10.1 changes two things:

- each LOS state is evaluated only for the links with a positive weight in it; for the others the old code added
  exactly 0;
- the links are processed in blocks of at most `BLOCK_LINKS` (20 000), so the largest arrays are about 10 MB.

The values are the same element by element (the blocker processes still draw all instants of a chunk first, in the
same order): `tests/test_blockage.py` compares the function with the 2.10.0 function, kept in the test file, with
`==` on random inputs and on whole runs, and the fingerprints and metrics of every measured pair below are equal.

Card `urban-grid-28ghz-beams` (40 users, 76 sites), walking speed, 8 s with 2 s warm-up (two chunks of 400 steps),
seed 3201 of the real-data runs, rule A3; card `urban-macro-tr37885-4ghz` default, 16 s, as a reference. One fresh
process per run, one at a time, 2.10.0 and 2.10.1 function alternating, median of three; the world build is not
timed; machine load 1-10 % throughout (NumPy 2.4.6, the same modest virtual machine):

| Case | Radio samples 2.10.0 | 2.10.1 | Ratio | Run-phase memory 2.10.0 | 2.10.1 |
|---|---|---|---|---|---|
| Blockage A, portrait | 97.0 s | 47.9 s | 2.03 | 2.12 GB | 0.58 GB |
| Blockage A, landscape | 95.6 s | 49.6 s | 1.93 | 2.12 GB | 0.56 GB |
| Blockage A with 8 SSB beams and angular spread | 150.9 s | 105.2 s | 1.44 | 2.12 GB | 0.58 GB |
| Reference (no blockage) | 0.77 s | 0.78 s | 1.0 | 0.23 GB | 0.21 GB |

One call of `factor_db` on a full chunk takes 19.9 s instead of 42.8 s and allocates 132 MB instead of 1744 MB.
The peak of the whole process fell from 2.12 GB to 0.87 GB; what remains is set by the world build (the radio map of the 76 sites), which this
version does not change; the target registered before the work was 0.8 GB for the whole process, so that target
was missed. Seven FR2 runs in parallel need about 6 GB instead of about 15 GB (estimated as 7 x 0.87 GB and 7 x 2.12 GB). With angular spread the remaining
time is mostly the beam gains over the angular spectrum, which this version does not change.

## Next steps

- Compiled kernels for the measurement instants (A3 entry times, the prepared set of conditional
  handover) behind the same switch, again accepted only with unchanged golden fingerprints.
- Batching parts of the measurement instants that are the same for every rule of a family (the
  A3 entry conditions and time-to-trigger of rules that differ only in their parameters).
- The world build (about 17 s for the default grid) dominates short jobs; the radio map could be
  stored and shared between the jobs of a study that use the same scenario and seed.
