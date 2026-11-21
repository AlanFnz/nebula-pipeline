# Studies

Choose **New piece** to start from text, a shape, a model or footage. **Open** loads a saved composition and displays recent projects. Saving a personal study makes it available from **Studies → Browse**.

An optional local library adds editable starting points to the same browser. On macOS, place the library folder (or a symbolic link to it) at `~/Library/Application Support/Nebula Studio/Study Library`. For a source checkout you can also set `NEBULA_STUDY_LIBRARY` to the library directory before launching the editor.

The library contains a version 1 `catalog.json` with a `studies` array. Each entry has an `id`, `name`, `date`, and optional `category`. The matching document lives at `studies/<id>.nebula`. IDs use lowercase letters, numbers, underscores and hyphens. Loading a study opens an editable copy. Use **Save** to keep your changes in a project.
