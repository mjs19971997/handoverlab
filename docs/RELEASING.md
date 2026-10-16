# Releasing HandoverLab

A release is made by pushing an annotated version tag `vX.Y.Z` to GitHub. The tag push starts
`.github/workflows/publish.yml`, which checks that the tag matches the package version
(`tools/release_check.py`), builds the source distribution and the wheel, checks them and uploads
them to PyPI with trusted publishing (no token is stored anywhere). The owner then creates a GitHub
release from the existing tag; the Zenodo GitHub integration archives that release and gives it a
DOI (Zenodo reacts only to GitHub releases, not to tags). The publish workflow also runs when the
release is published, and skips the files that are already on PyPI, so the release does not fail
and does not upload anything twice. Nothing is published by a push to a branch or a pull request.

The PyPI side is set up: a trusted publisher for the project `handoverlab`, owner
`mjs19971997`, repository `handoverlab`, workflow `publish.yml`, environment `pypi`.

## One-time set-up

1. **GitHub environment `pypi`.** In the repository on GitHub: *Settings > Environments*. The
   environment is created by the first run of the workflow if it does not exist; it can also be
   created by hand (*New environment*, name it exactly `pypi`). Optional: under *Deployment
   protection rules* add yourself as a *required reviewer* (every upload then waits for your
   approval on the run page), and under *Deployment branches and tags* choose *Selected branches
   and tags* and add the tag rule `v*`.
2. **Zenodo.** Sign in at <https://zenodo.org> with the GitHub account `mjs19971997`, open
   *Account > GitHub* (<https://zenodo.org/account/settings/github/>), press *Sync now* if the
   repository is not listed, and switch `mjs19971997/handoverlab` **on**. From then on every
   published GitHub release is archived with the metadata in `.zenodo.json` (title, authors,
   licence, keywords). Zenodo creates a concept DOI for all versions and one DOI per version.

## Making a release

1. **Check that `main` is green**: the `tests` and `docs` workflows of the last commit on
   *Actions*, and the latest `nightly` run.
2. **Set the version** in a commit on `main`:
   - `pyproject.toml`: `version = "X.Y.Z"` (and the *Development Status* classifier if it
     changes);
   - `src/handoverlab/__init__.py`: `__version__ = "X.Y.Z"`;
   - `CITATION.cff`: `version: "X.Y.Z"` and `date-released:` the release date;
   - `CHANGELOG.md`: move the entries of *Unreleased* into `## [X.Y.Z] - <release date>`, keep an
     empty `## [Unreleased]` on top, and set the links at the end to

     ```text
     [Unreleased]: https://github.com/mjs19971997/handoverlab/compare/vX.Y.Z...HEAD
     [X.Y.Z]: https://github.com/mjs19971997/handoverlab/compare/vPREVIOUS...vX.Y.Z
     ```

   - README, `docs/index.md` and `docs/user_guide.md`: the status line and the version named.
3. **Check the metadata and the build locally**:

   ```bash
   python tools/release_check.py --tag vX.Y.Z       # versions, changelog, citation, .zenodo.json
   python -m pip install build twine
   python -m build                                   # dist/handoverlab-X.Y.Z.tar.gz and the wheel
   python -m twine check --strict dist/*
   python -m pytest -q
   ```

   Commit, push, and wait until the workflows of the commit are green.
4. **Tag and push the tag**; this publishes to PyPI:

   ```bash
   git tag -a vX.Y.Z -m "HandoverLab X.Y.Z"
   git push origin vX.Y.Z
   ```

   The `publish` workflow starts. If the environment has a required reviewer, approve the `pypi`
   deployment on the run page. The workflow checks the tag against the version, builds, runs
   `twine check`, installs the wheel and runs a quick verification, and uploads.
5. **Create the GitHub release from the existing tag** (this gives the Zenodo DOI): *Releases >
   Draft a new release*, *Choose a tag*: pick the existing `vX.Y.Z`; title `HandoverLab X.Y.Z`;
   paste the changelog section as the description; leave *Set as a pre-release* unticked for a
   final release; press **Publish release**. The `publish` workflow runs again and skips the files
   that are already on PyPI.
6. **Check the result**:
   - <https://pypi.org/project/handoverlab/> shows the version, and
     `pip install handoverlab==X.Y.Z` in a fresh environment followed by
     `handoverlab verify --only pathloss fingerprints` passes;
   - Zenodo shows the new version with a DOI (*Account > GitHub*, or the Zenodo record). After the
     first archived release, add the DOI badge and the concept DOI to `README.md` and as `doi:` to
     `CITATION.cff` in a follow-up commit.

A pre-release (for example `1.1.0rc1`, tag `v1.1.0rc1`) is published the same way; PyPI treats it
as a pre-release and `pip` installs it only on request. Tick *Set as a pre-release* when creating
its GitHub release.

A file once uploaded to PyPI cannot be replaced, and a tag that has been published to PyPI must
not be moved or deleted: if something is wrong after the upload, fix it and release the next patch
version.

## If the upload fails

- *invalid-publisher* or *environment mismatch*: the workflow file name (`publish.yml`), the
  environment name (`pypi`), the owner and the repository must match the trusted publisher on PyPI
  exactly.
- *Waiting for review* or *deployment rejected*: the `pypi` environment has a required reviewer or
  a deployment rule; approve the deployment on the run page, or allow the tag rule `v*` under
  *Deployment branches and tags*.
- *tag does not match the package version*: the tag and the version in `pyproject.toml` differ.
  Nothing was uploaded, so the tag can be deleted, the version fixed, and the tag pushed again.
- The workflow can be started again from its run page (*Re-run jobs*) once the cause is fixed;
  files already on PyPI are skipped (`skip-existing`).
