# Nebula development

When reconstructing a reference or adding a study, first inspect the existing
sources, effects and parameters. Reuse them where appropriate; extend a related
capability before creating a parallel implementation. Add new tools when the
visual or functional requirement is genuinely different. Keep useful controls
editable so the study can become a starting point for new work.

Preserve existing studies, their saved values and rendering contracts. New
behavior must be opt-in or versioned. Compare the actual rendered motion and
appearance with the reference, not only isolated stills.

Keep generated media, local project files and render caches out of commits.
See docs/development.md and VERSIONING.md for build and validation guidance.

Use lowercase conventional commit subjects: `type(scope): description` or
`type: description`. Keep each commit focused on one change. Supported types
are `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`, `ci`, `chore`,
`revert` and `merge`; the optional scope is lowercase. Body text may retain
case-sensitive identifiers. Never rewrite published history without explicit
authorization. Enable the repository hook with `git config core.hooksPath .githooks`.

Application code belongs in the relevant `nebula/` package; keep the root launchers
thin. Use explicit package imports and `nebula.resources` for bundled assets.
Preserve legacy entry points and rendering compatibility modules unless their
removal has been separately justified. See the code map in docs/development.md.
