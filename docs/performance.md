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

## Next steps

- Compiled kernels for the measurement instants (A3 entry times, the prepared set of conditional
  handover) behind the same switch, again accepted only with unchanged golden fingerprints.
- Batching parts of the measurement instants that are the same for every rule of a family (the
  A3 entry conditions and time-to-trigger of rules that differ only in their parameters).
- The world build (about 17 s for the default grid) dominates short jobs; the radio map could be
  stored and shared between the jobs of a study that use the same scenario and seed.
