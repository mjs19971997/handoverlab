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

## Next steps

The design plans further engine steps for a later stage, each accepted only if the golden
fingerprints stay unchanged: moving work that changes only at measurement instants out of the step
loop, batching the engines of all rules of a job into one array dimension, and optional compiled
kernels for the link-monitoring and condition loops behind a switch, with the NumPy path as the
reference.
