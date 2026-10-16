# Releasing HandoverLab

A release is made by the owner of the repository by publishing a GitHub release. Publishing the
release starts `.github/workflows/publish.yml`, which builds the source distribution and the wheel,
checks them and uploads them to PyPI with trusted publishing (no token is stored anywhere). The
Zenodo GitHub integration archives the same release and gives it a DOI. Nothing is published by a
push, a tag alone or a pull request.

The PyPI side is already set up: a pending trusted publisher for the project `handoverlab`, owner
`mjs19971997`, repository `handoverlab`, workflow `publish.yml`, environment `pypi`.

## One-time set-up

1. **GitHub environment `pypi`.** In the repository on GitHub: *Settings > Environments > New
   environment*, name it exactly `pypi`, and save. Recommended: under *Deployment protection
   rules* add yourself as a *required reviewer* (every upload then waits for your approval), and
   under *Deployment branches and tags* choose *Selected branches and tags* and add the tag rule
   `v*`.
2. **Zenodo.** Sign in at <https://zenodo.org> with the GitHub account `mjs19971997`, open
   *Account > GitHub* (<https://zenodo.org/account/settings/github/>), press *Sync now* if the
   repository is not listed, and switch `mjs19971997/handoverlab` **on**. From then on every
   published GitHub release is archived with the metadata in `.zenodo.json` (title, authors,
   licence, keywords). Zenodo creates a concept DOI for all versions and one DOI per version.

## Release 1.0.0

The repository is at 1.0.0rc2. For the final release:

1. **Check that `main` is green**: the `tests`, `lint` and `docs` workflows of the last commit on
   *Actions*, and the latest `nightly` run.
2. **Set the version to 1.0.0** in a commit on `main`:
   - `pyproject.toml`: `version = "1.0.0"` and the classifier
     `Development Status :: 5 - Production/Stable`;
   - `src/handoverlab/__init__.py`: `__version__ = "1.0.0"`;
   - `CITATION.cff`: `version: "1.0.0"` and `date-released:` the release date;
   - `CHANGELOG.md`: merge the sections `## [1.0.0rc2]` and `## [1.0.0rc1]` into
     `## [1.0.0] - <release date>` (add any later entries from *Unreleased*), and change the links
     at the end to

     ```text
     [Unreleased]: https://github.com/mjs19971997/handoverlab/compare/v1.0.0...HEAD
     [1.0.0]: https://github.com/mjs19971997/handoverlab/compare/e93b9c59e5a42665a47be91922ddd5aede998367...v1.0.0
     ```

   - README and `docs/index.md`: the status line.
3. **Check the metadata and the build locally**:

   ```bash
   python tools/release_check.py --tag v1.0.0       # versions, changelog, citation, .zenodo.json
   python -m pip install build twine
   python -m build                                   # dist/handoverlab-1.0.0.tar.gz and the wheel
   python -m twine check --strict dist/*
   python -m pytest -q
   ```

   Commit, push, and wait until the workflows are green.
4. **Tag and publish the release** on GitHub: *Releases > Draft a new release*, *Choose a tag*:
   type `v1.0.0` and pick *Create new tag on publish*, target `main`; title `HandoverLab 1.0.0`;
   paste the changelog section as the description; leave *Set as a pre-release* unticked; press
   **Publish release**.
   (Or from the command line: `git tag -a v1.0.0 -m "HandoverLab 1.0.0" && git push origin v1.0.0`,
   then draft the release from that tag and publish it.)
5. **Approve the upload**: the `publish` workflow starts; if the environment has a required
   reviewer, approve the `pypi` deployment on the run page. The workflow checks that the tag
   matches the version (`tools/release_check.py`), builds, runs `twine check` and uploads.
6. **Check the result**:
   - <https://pypi.org/project/handoverlab/> shows 1.0.0, and
     `pip install handoverlab==1.0.0` in a fresh environment followed by
     `handoverlab verify --only pathloss fingerprints` passes;
   - Zenodo shows the new version with a DOI (*Account > GitHub*, or the Zenodo record); add the
     DOI badge and the concept DOI to `README.md` and as `doi:` to `CITATION.cff` in a follow-up
     commit, and add a new empty *Unreleased* section if it is missing.

## Later releases

The same steps with the new version number: a version commit (`pyproject.toml`, `__init__.py`,
`CITATION.cff`, a `## [x.y.z]` changelog section with its compare link
`compare/vPREVIOUS...vx.y.z` and `[Unreleased]: compare/vx.y.z...HEAD`), `tools/release_check.py
--tag vx.y.z`, then a published GitHub release with the tag `vx.y.z`. A pre-release (for example
`1.1.0rc1`, tag `v1.1.0rc1`) is published the same way with *Set as a pre-release* ticked; PyPI
treats it as a pre-release and `pip` installs it only on request.

A file once uploaded to PyPI cannot be replaced: if something is wrong after the upload, fix it and
release the next patch version.

## If the upload fails

- *invalid-publisher* or *environment mismatch*: the workflow file name (`publish.yml`), the
  environment name (`pypi`), the owner and the repository must match the trusted publisher on PyPI
  exactly.
- *tag does not match the package version*: the tag and the version in `pyproject.toml` differ;
  delete the release and the tag, fix the version, and publish again.
- The workflow can be started again from its run page (*Re-run jobs*) once the cause is fixed;
  `skip-existing` is not set, so a version already on PyPI fails loudly instead of being skipped.
