# Versioning

Nebula uses one project version for its desktop app and existing pipeline. The canonical value is `__version__` in [`_version.py`](_version.py). The desktop CLI (`python studio.py --version`), Qt application metadata and window title read it directly. Both macOS bundle version fields are derived copies, maintained by `scripts/sync_version.py`.

## Convention

Use `MAJOR.MINOR.PATCH` and Git tags named `vMAJOR.MINOR.PATCH`.

- During `0.x` development, increment **MINOR** for new milestones or intentional changes to preset/rendering behavior; increment **PATCH** for compatible fixes and documentation/packaging corrections.
- At `1.0.0`, establish a stable public compatibility contract. After that, incompatible changes increment **MAJOR**, compatible features increment **MINOR**, and compatible fixes increment **PATCH**.
- Record rendering changes explicitly in the changelog even when JSON presets still load. Reproducible historic output requires the corresponding tag, seed, settings, source and compatible dependency versions. Dependencies are currently range-based, so the version tag alone does not pin the complete rendering environment.
- Create annotated tags only for tested milestones. Never move or replace a published tag. Untagged development commits do not constitute a release; the working version remains the last milestone until the next version bump.

`v0.0.1` is the existing initial pipeline tag. `v0.1.0` marks the first desktop milestone and the new deterministic rendering behavior. Existing tags remain unchanged. A Git tag does not imply a signed installer or a GitHub Release.

## Preparing a milestone

1. Edit `_version.py` and add dated notes to `CHANGELOG.md`.
2. Run `.venv/bin/python scripts/sync_version.py` to update the committed macOS metadata.
3. Run `.venv/bin/python scripts/sync_version.py --check`, `.venv/bin/python studio.py --version`, the focused test suite and `git diff --check`.
4. Review and commit only the intended source, tests, metadata and documentation. Keep local environments, caches, presets, QA captures, reference clips and generated media out of Git.
5. Create an annotated `vMAJOR.MINOR.PATCH` tag on the tested commit and push the intended branch and that exact tag explicitly. Do not push all tags or merge into `main` as part of this procedure.

No release automation or public GitHub Release is required.
