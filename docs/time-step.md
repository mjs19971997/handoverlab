# Does the 10 ms step change the results?

HandoverLab advances in steps of `protocol.step_s` (10 ms by default). LTM commands take 3-10 ms and DAPS
interrupts the user plane for a few milliseconds, so a coarse step could shift results. This page reports a check
of 2.1.0 whose criteria were fixed before the runs: the same scenarios at 10, 5, 2 and 1 ms.

## Set-up (fixed before the runs)

| Case | Scenario | Rules | Runs |
|---|---|---|---|
| T-a | `urban-grid-10ghz`, 40 users, 60 s (10 s warm-up) | A3 (3 dB, 160 ms), CHO, LTM, DAPS (defaults) | seeds 1-10 per step |
| T-b | `urban-grid-28ghz-beams` (SSB beams, beam failure recovery), 20 users, 30 s (5 s warm-up) | A3 (3 dB, 160 ms), LTM | seeds 1-10 per step |

Criterion per case, rule and metric: the 10 ms step is adequate if the mean over the seeds differs from the 1 ms
mean by at most 5 %, or by at most 0.05 per UE-minute for rates below 1 per UE-minute, or by at most 1 ms per
handover for the interruption.

## Result

**All 30 criteria are met at 10, 5 and 2 ms.** The metrics are identical seed by seed at all four steps; the event
logs differ only in event times within a step.

| Case | Rule | Handovers / UE-min | Unnecessary | Failures | Interruption per handover [ms] |
|---|---|---|---|---|---|
| T-a | A3 | 11.481 (same at 1 ms) | 1.236 (same) | 0.036 (same) | 45.25 (same) |
| T-a | CHO | 11.637 (same) | 1.350 (same) | 0.000 (same) | 40.02 (same) |
| T-a | LTM | 13.050 (same) | 2.763 (same) | 0.003 (same) | 20.33 (same) |
| T-a | DAPS | 11.484 (same) | 1.239 (same) | 0.033 (same) | 2.87 (same) |
| T-b | A3 | 25.236 (same) | 8.268 (same) | 0.876 (same) | 79.65 at 10 ms, 79.57 at 1 ms |
| T-b | LTM | 30.660 (same) | 14.196 (same) | 0.132 (same) | 23.44 at 10 ms, 23.42 at 1 ms |

Ping-pong rates are identical too. The differences of the interruption come from executions that wait for the
target while T304 runs: the wait ends at the next step.

## Why the step hardly matters

- Handover decisions are taken at the measurement instants (L1 period 40 ms), and the time-varying part of the
  channel and the L1 measurement error are drawn once per measurement, not per step.
- Interruptions are accounted with their configured length (for example 2 ms for DAPS), not rounded to the step.
- What the step does round is the time a delayed event takes effect (a command, the end of an execution, a
  timer): it is applied at the first step at or after its due time, at most one step late.

## Exploratory checks (after the result above; not part of the fixed plan)

| Check | Result |
|---|---|
| Delays that are not multiples of 10 ms: `urban-grid-10ghz`, 20 users, 30 s, seeds 1-10; A3 with `prep_s` 25 ms and `exec_s` 45 ms, LTM with `cmd_delay_s` 3 ms and `exec_s` 15 ms; 10 against 1 ms | every metric identical seed by seed; interruption per handover 47.15 / 47.16 ms (A3), 15.00 / 15.00 ms (LTM) |
| The card `smoke` (20 users, 30 s), A3 and CHO, seeds 1-10, 10 against 1 ms | one seed of ten differs by one handover: handovers -0.6 %, unnecessary handovers -1.5 % at 10 ms; failures and ping-pong identical |

## Reading

For the handover metrics of HandoverLab the 10 ms step is adequate: in these runs it changes no rate by more than
1.5 %, and the interruption by less than 0.1 ms per handover. Use 1 ms only when an event must take effect within
a few milliseconds of its due time, and check with `protocol.step_s` (the L1 period must stay a whole multiple of
it). A model with a scheduler per slot, planned for a later release, will need a step of one slot.
