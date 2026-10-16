# Tutorial 3: a fair tuning study

Comparing a new handover rule with a baseline on one hand-picked setting each tells you little:
a baseline tuned with less care makes any new rule look good. A *study* removes that freedom. Every
rule is tuned on its own seeds with the same number of evaluated settings and a selection rule that
is fixed in advance; automatic gates check that the tuning means something; then the selected
settings are compared on fresh seeds, paired by seed. This tutorial runs the example study
[`examples/study_smoke.yaml`](https://github.com/mjs19971997/handoverlab/blob/main/examples/study_smoke.yaml)
(about seven minutes with two workers) and explains each step.

## 1. The study file

```yaml
name: study-smoke
scenario:
  base: smoke
  radio: {isolation: 1.0}           # no beam isolation: more interference, so that failures occur
  mobility: {users: 12, profile: veh30}
  run: {duration_s: 20.0, warmup_s: 4.0}
conditions:
  layout.site_spacing_m: [100.0, 150.0]
seeds:
  tuning: [901, 902, 903, 904]      # never used in the test stage
  test: {first: 1, last: 6}
tuning:
  settings: 8                       # every tuned method evaluates 8 settings per group
  random: 5                         # 5 drawn at random, then 3 around the best of them
  reference: {rule: a3, name: A3-ref, off_db: 3.0, ttt_s: 0.16}
  budgets: {standard: 1.0, strict: 0.5}   # shares of the reference failure rate
  group_by: [layout.site_spacing_m] # tune per site spacing
  min_reference_failures: 3
  extend_steps: 2
  max_extensions: 2
  gates: {grid_edge: extend, budget_binding: warn, budget_met: warn, equal_budget: block,
          seed_overlap: block, flat_optimum: warn}
methods:
  A3:
    rule: a3
    grid: {off_db: [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0], ttt_s: [0.0, 0.04, 0.08, 0.16, 0.32]}
    natural_bounds: {ttt_s: lower}  # 0 s is a floor, not an edge of the search
  CHO:
    rule: cho
    fixed: {o_prep_db: -2.0, n_max: 4}
    grid: {o_exec_db: [0.0, 1.0, 2.0, 3.0, 4.0, 5.0], ttt_exec_s: [0.0, 0.04, 0.08, 0.16, 0.32]}
    natural_bounds: {ttt_exec_s: lower}
compare:
  baseline: A3-ref
  metrics: [unnecessary_pm, failures_pm, handovers_pm, prepared_cells_mean]
output: results/study-smoke
```

The design decisions are all in the file, before any result exists:

- **What is compared, where.** Two conditions (site spacing 100 and 150 m); the rules are tuned
  per site spacing, as an operator tunes a deployment.
- **Separate seeds.** Tuning seeds 901-904, test seeds 1-6. The gate `seed_overlap` blocks a study
  that mixes them.
- **Equal effort.** A3 and CHO both evaluate 8 settings per group: 5 drawn at random from the grid
  (with a generator seeded by the method name), then 3 one or two grid steps around the best.
- **The selection rule.** The failure budget is a share of the failure rate of the reference rule
  `A3-ref` on the tuning runs (`standard` = the same rate, `strict` = half). Among the settings
  within a budget, the lowest unnecessary-handover rate wins; settings within 5 % of it count as
  equal and are ordered by preparation overhead, then failure rate. Each tuned method gets one
  selected setting per budget, named `A3@standard`, `A3@strict` and so on.
- **Natural bounds.** A time-to-trigger of 0 s is a physical floor. Declaring it keeps the
  grid-edge gate from complaining when the selection sits there.

## 2. Look before you run

```bash
handoverlab study examples/study_smoke.yaml --dry-run
```

```text
study study-smoke: 2 condition(s), 4 tuning seed(s), 6 test seed(s)
tuning: 2 group(s) (layout.site_spacing_m=100, layout.site_spacing_m=150), 8 settings per method (5 random, then refinement), budgets standard = 1 x reference, strict = 0.5 x reference
  A3           rule a3     grid off_db: 7 values, ttt_s: 5 values (35 settings)
  CHO          rule cho    grid o_exec_db: 6 values, ttt_exec_s: 5 values (30 settings)
stage tune1: 8 jobs, 88 rule runs
stage tune2: 8 jobs, up to 48 rule runs
gate seed_overlap: pass (tuning and test seeds are disjoint (4 and 6 seeds))
stage test: 12 jobs x 5 rules (A3-ref, A3@standard, A3@strict, CHO@standard, CHO@strict)
baseline of the paired comparisons: A3-ref
```

A *job* is one world (condition and seed) with all its rules; the rules of a job share the radio
samples.

## 3. Run it

```bash
handoverlab study examples/study_smoke.yaml --workers 2 --report
```

```text
study study-smoke -> results/study-smoke (2 workers)
stage tune1: 8 jobs (88 rule runs), 0 done earlier
stage tune2: 8 jobs (48 rule runs), 0 done earlier
  extend A3.off_db at the upper end by 7.0, 8.0 (extension 1 of at most 2); tuning again
stage tune1: 8 jobs (88 rule runs), 0 done earlier
stage tune2: 8 jobs (48 rule runs), 0 done earlier
  gate warn budget_binding (layout.site_spacing_m=150, budget standard): the reference rule has only 1 failure on the tuning runs (minimum 3); share of settings within the budget: A3 62 %, CHO 62 %
  gate warn budget_binding (layout.site_spacing_m=150, budget strict): the reference rule has only 1 failure on the tuning runs (minimum 3); share of settings within the budget: A3 25 %, CHO 62 %
stage test: 12 jobs (60 rule runs), 0 done earlier
study study-smoke: complete
```

(Lines for each finished job are left out.) Two things happened between tuning and test.

**The grid was widened.** In the first tuning round A3 selected `off_db = 6`, the largest value of
its grid, in three of the four group-budget pairs. A setting on the edge means the search may have
stopped too early, and a baseline tuned that way can make another rule look better than it is. With
`grid_edge: extend` the study added 7 and 8 dB (the spacing of the last two values) and tuned *every*
method again with the same budget of 8 settings. Rule runs that had already been simulated were
reused. After the extension A3 still selects 6 dB, now an interior value, and the gate passes. The
extension is recorded with its date in `results/study-smoke/AMENDMENTS.md`:

```text
## Extension 1 (2026-10-16T00:03:16+00:00)

- `A3.off_db`: added 7.0, 8.0 at the upper end (grid before: 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0);
  selected at the edge in layout.site_spacing_m=100, budget standard; layout.site_spacing_m=100,
  budget strict; layout.site_spacing_m=150, budget standard.
```

With `grid_edge: block` (the default) the study would have stopped here and asked you to widen the
grid; with `warn` it would have gone on and only flagged the edge. `max_extensions` caps the number
of extension rounds; if the edge remains after the last one, the gate blocks.

**Two warnings remain.** At 150 m the reference rule failed only once on the four tuning runs, so a
budget of "the reference failure rate" rests on a single event. The study goes on (`budget_binding`
is a warning by default), but the report shows it next to every result. In a real study this is
the cue to add tuning seeds or lengthen the runs.

## 4. Stop, resume, check progress

A study can be stopped at any time (Ctrl+C) and run again with the same command: every job writes
one record when it finishes, and finished jobs are skipped. Changing the study file re-runs only
the jobs it affects. While a study runs, or after you stopped it, ask what is left:

```bash
handoverlab status results/study-smoke
```

```text
study study-smoke in results/study-smoke
  last session (1) 2026-10-15T23:59:30+00:00: stopped after tuning
  stage    jobs   done  failed  to run  rule runs
  tune1       8      8       0       0          0
  tune2       8      8       0       0          0
  test       12      0       0      12         48
  gates: pass (0 blocking, 5 warnings)
  time left: about 34 s with 2 workers (69 s CPU; measured on 16 jobs: world 2.5 s, 3.36 s per rule run of 1000 user-seconds)
```

(This output is from a run of the same study with `grid_edge: warn`, stopped after tuning with
`--tuning-only`; hence five warnings.) The time left is
estimated from the jobs this study has already finished.

## 5. What makes it fair

| Risk | What the study does |
|---|---|
| the new rule is tuned more carefully than the baseline | equal number of evaluated settings per method (`equal_budget` gate) |
| settings are chosen on the test data | separate tuning and test seeds (`seed_overlap` gate) |
| the choice is made after looking at the results | the selection rule is in the file; every evaluated setting is stored |
| the search stopped too early | `grid_edge` gate (block, warn or extend) |
| the failure budget constrains nothing | `budget_binding` gate |
| the winner is chosen by tie-breaks | `flat_optimum` gate |
| differences between worlds hide the effect | rules share worlds and radio samples; paired tests |

What the study does *not* check is whether the scenario fits your question. That remains your job.

## Next

[Tutorial 4](reading-the-report.md) reads the report this study wrote.
