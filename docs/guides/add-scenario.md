# How to add a scenario

There are two ways: a scenario of your own in a configuration file (nothing to install), or a new
built-in scenario with a scenario card (a contribution to HandoverLab).

## Your own scenario in a file

Start from the built-in scenario closest to what you need and change only what differs. The key
`base` names it; every other key overrides a value, with the same names as in the
[user guide](../user_guide.md#scenario-keys-and-defaults):

```yaml
schema: 1
scenario:
  base: urban-grid-10ghz
  name: dense-grid-28ghz
  layout: {blocks: [4, 4], site_spacing_m: 75}
  radio: {carrier_ghz: 28.0, bandwidth_mhz: 400}
  mobility: {users: 80, profile: veh30}
  run: {duration_s: 180, warmup_s: 20}
seeds: [1, 2, 3]
rules:
  - {rule: a3, off_db: 3.0, ttt_s: 0.16}
  - {rule: cho, o_prep_db: -2.0, o_exec_db: 3.0}
output: results/dense-grid.csv
```

Every key is checked: a misspelt key or a value out of range stops the run with the full key name.
Check the file without running it:

```bash
python -c "import handoverlab as hl; print(hl.load_config('dense.yaml').scenario)"
handoverlab run dense.yaml --seeds 1 --debug     # one seed with the engine invariants checked
```

Explicit site positions replace the regular placement (`layout.sites: [[0, 0], [150, 0], ...]`,
in metres). In Python the same is `hl.builtin_scenario("urban-grid-10ghz").with_overrides({...})`
with dotted keys such as `"layout.site_spacing_m"`. The same `scenario` block works in a
[study file](../tutorials/tuning-study.md), where `conditions` then vary single keys.

Before you trust results from a new scenario, look at it: `handoverlab gui` draws the layout and
the users, and a short run with `--events FILE --event-level full` shows every procedure (see
[export event logs](export-event-logs.md)).

## A new built-in scenario

A built-in scenario is a YAML *card* in `src/handoverlab/scenarios/cards/`. The card holds the
values that differ from the defaults and documents them:

```yaml
# Scenario card (machine-readable).  docs/scenarios/dense-grid-28ghz.md is generated from this file.
name: dense-grid-28ghz
title: Dense street grid at 28 GHz
since: 1.1.0
purpose: >
  What the scenario is for and what it is not for.
layout_note: >
  How the layout relates to the standard it follows.
scenario:
  name: dense-grid-28ghz
  layout: {blocks: [4, 4], site_spacing_m: 75.0}
  radio: {carrier_ghz: 28.0, bandwidth_mhz: 400.0}
sources:                      # one entry for every value set above
  layout.site_spacing_m: "assumption (dense small cells)"
  radio.carrier_ghz: "TR 38.901 (FR2)"
  radio.bandwidth_mhz: "TS 38.101-2 (400 MHz channel)"
limitations:
  - "What the scenario does not model."
references:
  - "What its results were checked against."
```

Then:

1. Generate the documentation page and the layout drawing:
   `handoverlab scenarios --docs docs/scenarios`.
2. Add the page to `nav` in `mkdocs.yml` (under *Guides > Scenario cards*) and to the table of
   built-in scenarios in the user guide.
3. Run the tests: `tests/test_scenarios.py` checks that every value has a source and that the
   documentation page is current.
4. Add a line to `CHANGELOG.md` under *Added*. A new built-in scenario is a minor-release change;
   changing the values of an existing one changes results and is a major one (see
   [stability](../stability.md)).
