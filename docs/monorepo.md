# Run the pipeline from a Kotlin subdirectory

1. Keep the actual Gradle project in `kotlin/`, including its wrapper,
   settings, locks and verification metadata. A coordinating Gradle build can
   include existing Kotlin projects when relocation would disrupt consumers.
2. Copy [kotlin-quality.yml](../.github/workflows/kotlin-quality.yml) to the
   repository-root `.github/workflows/` directory. Put the template's
   `scripts/` and pipeline tests under `kotlin/`, then adapt the
   [caller](../examples/monorepo/kotlin.yml).
3. Override `fast-tasks` and `test-tasks` to match the enabled Gradle targets.
   Add exact paths for included builds outside `kotlin/`, shared build inputs,
   and fixture directories to `additional-paths`. Paths are relative to the
   repository root, one per line.
4. Require the caller's **quality / Pipeline Status** check. Keep native, iOS,
   Android, Wasm or other target jobs that need a different SDK or runner in the
   caller and include them in the repository's required checks.

Unrelated changes leave the terminal Kotlin status green and skip Gradle.
Changing the Kotlin project, a shared input or a workflow runs the relevant jobs.
Set `versioning: true` if this project uses the template's root-level
`version=MAJOR.MINOR.PATCH` and its own `.changeset/` directory. Set
`build-docker: true` only when the project has a compatible `stageRuntime`
task and Dockerfile. The reusable workflow uses read permissions. Keep
publishing in the parent repository's release workflow and share its writer
concurrency group across all languages.

For UI, the existing Kotlin parser, renderer and Compose example are published
from separate source directories. The coordinating `./kotlin` build should
preserve their public coordinates and tests, including the shared parser,
renderer, design token and case-study fixtures. Keep the existing Android and
iOS runners while moving their entry points.
