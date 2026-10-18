## What and why

<!-- One topic per pull request. -->

## Does it change results?

<!-- "No", or which metrics or fingerprints change for which configurations, and why. -->

## Checklist

- [ ] `python -m pytest` passes
- [ ] `ruff check .` passes
- [ ] `handoverlab verify` passes (or the changed fingerprints are regenerated and explained)
- [ ] `CHANGELOG.md` has an entry under "Unreleased"
- [ ] New public names or configuration keys: snapshot updated
      (`python -m handoverlab.stability --write tests/data/public_api.json`)
- [ ] New code comes with tests (coverage does not fall)
