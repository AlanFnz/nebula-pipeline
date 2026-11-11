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
