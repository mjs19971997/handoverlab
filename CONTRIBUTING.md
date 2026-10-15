# Contributing to HandoverLab

Thank you for your interest. Bug reports, questions, new handover rules, scenarios and
documentation improvements are all welcome.

## Reporting a problem

Open an issue with:

- what you ran (the configuration file or a short script) and the seed;
- what you expected and what happened (error message, or the metric that looks wrong);
- the output of `python -c "import handoverlab.io as i; print(i.provenance())"`.

## Development set-up

```bash
git clone https://github.com/mjs19971997/handoverlab.git
cd handoverlab
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install -e ".[test]"
python -m pytest
```

The test suite runs in a few minutes; `handoverlab verify` adds a verification report. Keep new tests
small: a few users, tens of seconds of
simulated time, a 2 x 2-block grid or a coarse radio map.

## Rules for code changes

- **Determinism.** Everything random must come from the streams in `handoverlab.seeds` (or, inside a
  rule, from `ctx.rng`). Never use NumPy's global random state or Python's `random` module. The same
  seed must give identical metrics and event logs.
- **Results change only on purpose.** If a change alters the metrics of an existing configuration,
  say so in the pull request and in `CHANGELOG.md`, with the reason. The regression test against
  the bh6 prototype (`tests/test_regression_bh6*.py`) must keep passing; if a model change makes it
  fail deliberately, explain why and update the reference in the same pull request. The golden
  event-log fingerprints (`handoverlab verify --only fingerprints`) protect every change, including
  speed-ups; a change that alters them on purpose regenerates them with
  `python -m handoverlab.verify.golden --write` and says why in `CHANGELOG.md`.
- **Model elements cite their source** (3GPP clause or a stated assumption) in the docstring.
- **Style.** Readable NumPy code, docstrings on public functions, lines up to 120 characters, an
  `# SPDX-License-Identifier: MIT` line at the top of each source file. Python 3.9 must keep working
  (no `match`, no `X | Y` type unions at run time).

## Adding a handover rule

Subclass `handoverlab.rules.BaselineRule` or `ConditionalRule`, implement the hooks (see the user
guide), register it with `@register_rule("name")` or an entry point, and add a test that runs it on
a synthetic world (see `tests/helpers.py`) and on a small scenario. Add a contract test with
`handoverlab.testing.check_rule`; if the rule reduces to a built-in rule for some parameters, pass
`reduces_to` so that both are checked to give identical event logs.

## Adding or changing a scenario

Built-in scenarios are YAML cards in `src/handoverlab/scenarios/cards`. Give the source of every
value that differs from the defaults, the limitations and the reference results, then regenerate
the documentation pages with `handoverlab scenarios --docs docs/scenarios` (a test checks that they
are current).

## Pull requests

- One topic per pull request, with tests.
- All CI jobs (Linux, Windows, macOS; Python 3.9-3.12) must pass.
- Add an entry under "Unreleased" in `CHANGELOG.md`.

By contributing you agree that your contribution is licensed under the MIT licence of the project.
