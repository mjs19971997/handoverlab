# Stability policy

From version 1.0.0 on, HandoverLab follows [Semantic Versioning](https://semver.org/) for its
public surface. This page says what the public surface is, what each kind of release may change,
and how something is deprecated before it goes.

## The public surface

| Part | Where it is defined |
|---|---|
| Configuration files: experiment and study keys, their meaning and defaults | [user guide](user_guide.md#3-configuration), `handoverlab.config`, `handoverlab.studies.config` |
| File formats: result CSV and JSON, event-log and trace tables, study directories | [user guide](user_guide.md), `handoverlab.io`, `handoverlab.eventlog` |
| Schema version of configuration and result files | `handoverlab.stability.SCHEMA_VERSION` (now 1) |
| Metric and count names and their definitions | [metric reference](reference/metrics.md), `handoverlab.engine.METRICS` |
| The rule interface: hooks, their arguments, the fields of `RuleContext`, `Observation`, `OutcomeRecord`, `FailureRecord`, the outcome labels and the registry | `handoverlab.rules`, version `handoverlab.stability.RULE_API_VERSION` (now 1) |
| Python names exported by `handoverlab`, `handoverlab.rules`, `handoverlab.studies`, `handoverlab.stability`, and the documented functions of `handoverlab.eventlog`, `handoverlab.testing`, `handoverlab.verify` and `handoverlab.stats` | [API reference](reference/api/index.md) |
| Commands and options of the command line | [command-line reference](reference/cli.md) |

Not public: modules and names starting with an underscore, the engine internals
(`handoverlab.engine.core`, `procedures`, `batch`), the dashboard page (`handoverlab.gui.app`), the
layout of the report pages, the wording of messages, and timing figures.

The test `tests/test_stability.py` compares the surface with a snapshot
(`tests/data/public_api.json`, written by `handoverlab.stability.public_surface`), so that no part
of it changes by accident.

## What a release may change

| Release | May | May not |
|---|---|---|
| Patch (2.0.x) | fix bugs, documentation and performance | change a result that was correct, or the surface |
| Minor (2.x.0) | add keys with defaults that keep earlier results, add metrics, rules, scenarios, commands, options, optional hook arguments and record fields; deprecate | remove or rename any part of the surface, change a default |
| Major (x.0.0) | remove what was deprecated, rename, change defaults and file formats | remove something that was not deprecated in a minor release before |

**Results.** The model version (`handoverlab.studies.MODEL_VERSION`, now 2) identifies the
simulation model. A change of what a run computes for the same inputs, such as a corrected
channel formula, raises it, is listed in the changelog with its effect and comes with new golden
fingerprints. Such a change is made only in a minor or major release, never in a patch, unless it
corrects a bug; study directories of the old model version then run their jobs again instead of
reusing them.

**File formats.** Every configuration and result file has the top-level key `schema` (a file
without it is schema 1). A new schema version comes only with a major release. HandoverLab reads
every schema up to its own and refuses a newer one with a message that names it, instead of
misreading it.

**Rules.** A rule written for interface version 1 runs unchanged on every 1.x and 2.x release (2.0.0 only
added hooks). New hooks
get a default implementation in the base class; new fields of the observation and the records are
only appended.

## Getting the results of an earlier major release

2.0.0 changed defaults (see [moving from 1.x to 2.0](migration-2.0.md)). `handoverlab.stability.LEGACY_1X`
holds the 1.x values of every changed key; with it (and `mobility.profile: veh16` on the urban-grid cards) a
configuration gives the 1.x event log bit for bit. Since 2.1.0 it also holds `radio.channel_detail: simple`
(the large-scale channel of 2.0.0 and 1.x), and `handoverlab.stability.LEGACY_CARDS` holds the old values of
the built-in cards that 2.1.0 changed (apply them after `LEGACY_1X` to a scenario built from such a card). `handoverlab verify --only fingerprints` checks this on
every golden run of 1.12.0 (section `fingerprints-1x`).

```python
from handoverlab.stability import LEGACY_1X
sc = hl.builtin_scenario("ns3-urban-3.5ghz").with_overrides(LEGACY_1X)
```

## Deprecation

Something that is to be removed or renamed is first deprecated in a minor release and removed at
the earliest in the next major release. While deprecated it keeps working and issues a
`HandoverLabDeprecationWarning` (a `FutureWarning`, so it is shown by default) that names the
version that deprecated it, the version that removes it and the replacement:

```python
from handoverlab.stability import deprecated, deprecated_alias

def old_option_used():
    deprecated("the key 'tuning.foo'", since="1.2", removed_in="2.0", instead="'tuning.bar'")

old_name = deprecated_alias(new_name, "old_name", since="1.2", removed_in="2.0")
```

A renamed metric keeps its old name in `handoverlab.stability.METRIC_ALIASES`; study files and
`handoverlab.stability.metric_name` accept the old name with a warning. The changelog lists every
deprecation under *Deprecated*. To turn the warnings into errors while testing your own code:
`python -W error::FutureWarning` or `filterwarnings = ["error::FutureWarning"]` for pytest.

## Changing the surface (for contributors)

1. Make the change in a backwards-compatible way where possible (a new key with a default that
   keeps earlier results, an alias for a new name).
2. Write the new snapshot: `python -m handoverlab.stability --write tests/data/public_api.json`,
   and check its diff: only additions belong in a minor release.
3. Document the change in the user guide or reference and in `CHANGELOG.md` (*Added*,
   *Changed*, *Deprecated* or *Removed*).
