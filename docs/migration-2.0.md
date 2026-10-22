# Moving from 1.x to 2.0

HandoverLab 2.0.0 changes defaults so that a scenario follows the 3GPP texts more closely. Results of the same
configuration therefore differ from 1.x; nothing else in the interface was removed except the scenario card
that 1.11.0 had deprecated. Every change has a switch that gives the 1.x behaviour back, and
`handoverlab verify --only fingerprints` checks that these switches reproduce every golden run of 1.x bit for
bit.

## What changed

| Change | 2.0 default | Source | 1.x |
|---|---|---|---|
| Speed of light in the breakpoint distances | `radio.breakpoint_c_mps: 3.0e8` | TR 38.901 Table 7.4.1-1, notes 1 and 5 | 299 792 458 m/s |
| Smallest distance the path-loss formulas are evaluated at | `radio.pl_min_distance_m: 10` | TR 38.901 Table 7.4.1-1, applicability range of RMa, UMa, UMi (10 m <= d2D); InH not limited | none |
| Urban mobility | `mobility.profile: v60` (every vehicle at 60 km/h in one of two lanes of 3.5 m) | TR 37.885 clause 6.1.2 option A and Table A-1 | `veh16` (52-63 km/h, lateral 0-3 m) |
| Handover command received while T310 runs | `protocol.cmd_during_t310: receive` | TS 38.331 5.3.5.5.2 | `lost` |
| T304 | `protocol.t304_s: 1.0` | TS 38.331 5.3.5.8.3 | none |
| Link monitoring restarts on a new cell | `protocol.rlm_holdoff_s: 0.2` | an interpretation of TS 38.133 8.1.2.2 | 0 |
| CHO configuration that arrives while T310 runs | received like a handover command when the link reaches Qout (with `cmd_during_t310: receive`) | TS 38.331 5.3.5.13 | lost |
| Model version of studies | `MODEL_VERSION = "2"`: study directories of 1.x run their jobs again | | `"1"` |
| Scenario card `highway-10ghz` | removed (deprecated in 1.11.0) | TR 37.885 / TR 36.885 | |

The cards `smoke`, `urban-grid-10ghz`, `fr3-urban-15ghz`, `urban-grid-28ghz-beams` and `open-area-10ghz` use
`v60`. The protocol changes are the 3GPP protocol profile of 1.9.0, which brought the handover failure rate
from about six times the range measured in commercial networks to just above it.

## Getting 1.x results back

```python
import handoverlab as hl
from handoverlab.stability import LEGACY_1X, LEGACY_CARDS

over = dict(LEGACY_1X, **LEGACY_CARDS["smoke"], **{"mobility.profile": "veh16"})   # LEGACY_CARDS: since 2.1.0
sc = hl.builtin_scenario("smoke").with_overrides(over)
```

In a configuration file, set the same keys:

```yaml
scenario:
  base: smoke
  radio: {breakpoint_c_mps: 299792458.0, pl_min_distance_m: 0.0, channel_detail: simple,
          ue_height_m: 1.5}           # channel_detail since 2.1.0; ue_height_m: the card value of 2.0.0
  protocol: {cmd_during_t310: lost, t304_s: null, rlm_holdoff_s: 0.0}
  mobility: {profile: veh16}          # only for the urban-grid cards listed above
```

Keys that a configuration sets itself keep their values; only defaults changed. For the removed highway card,
use `highway-tr37885-4ghz` or `highway-tr37885-30ghz`, or write its values out (2000 m road, roadside sites
every 500 m 35 m from the road, UMa at 10 GHz with 25 m masts, profile `hwy`).

## Added in 2.0.0

The NTN scenario (`layout.kind: ntn`, card `ntn-leo600-2ghz`, rule `cho_d2`, see the [NTN guide](guides/ntn.md)),
the rule hook `ConditionalRule.exec_condition`, `RuleContext.cell_center`, and the optional `verify` group `ntn`.
