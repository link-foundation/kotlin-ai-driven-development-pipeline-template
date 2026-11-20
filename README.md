# Kotlin AI-Driven Development Pipeline Template

A runnable Kotlin Multiplatform library with JVM and Node.js targets, a JVM
entry point, and a GitHub Actions pipeline for pull requests and releases.
Use it at the repository root or from an existing multi-language repository.

## Quick start

Use this repository as a GitHub template or copy its files. Set the project name
in [settings.gradle.kts](settings.gradle.kts), the Maven group in
[gradle.properties](gradle.properties), and the POM metadata in
[build.gradle.kts](build.gradle.kts) before the first release.

Install JDK 21 and Node.js 24. The checked-in Gradle Wrapper verifies the
distribution checksum. The sample targets Java 17 bytecode.

```sh
./gradlew ktlintCheck detekt compileTestKotlinJvm compileTestKotlinJs
./gradlew jvmTest jsNodeTest
./examples/kotlin/run-greeting.sh Ada
```

Use `gradlew.bat` on Windows. The example prints `Hello, Ada!`.

## CI checks

- GitHub Actions compares a pull request with the current target branch, merges
  that same target commit into each applicable job, and selects checks from
  the resulting changes. Markdown changes run documentation checks without
  compiling Kotlin. Workflow changes also run actionlint and zizmor.
- The pipeline checks incoming Git history for credentials, validates the Gradle
  Wrapper, caps code files at 1,500 lines and Markdown at 2,500, and runs ktlint,
  Detekt and test compilation before executing both target suites. Test reports
  are retained as workflow artifacts.
- OSV-Scanner audits the committed Gradle dependency locks, Gradle verification
  metadata, and npm lockfiles with a fail threshold of any known advisory. The
  scheduled workflow also runs the audit on unchanged code, checks external
  links, and reports stale Dependabot pull requests.
- Container jobs test the same JVM distribution on native amd64 and arm64
  runners. The required result stays present for docs-only and unrelated
  changes. Configure branch protection to require **quality / Pipeline Status**
  and require branches to be up to date, or use a merge queue.

Enable the local Git hook with `git config core.hooksPath .githooks`. See
[Contributing](CONTRIBUTING.md) for formatting, dependency updates and changesets.

## Releases

Open a pull request with a [changeset](.changeset/README.md) for production
changes. GitHub Actions validates the release plan on the PR and releases on a
push to `main`. You can also dispatch **Kotlin pipeline** with
`operation=release` on `main` to retry or release pending changes.

The writer uses the highest pending semantic-version bump, updates the changelog
and commits only release metadata. It pushes the commit and matching version tag
atomically, then publishes checksummed JVM runtime and Maven repository archives
as GitHub Release assets. The first template changeset releases `v0.1.0`.
See [release setup and recovery](docs/releases.md) for branch rules, Maven Central
and multi-platform GHCR publishing.

## Multi-language repositories

Place the Gradle project and its helper scripts in `./kotlin`. Add a small
caller under the repository-root `.github/workflows` and set
`project-directory: kotlin`. List any shared fixture directories in
`additional-paths` so their changes still run Kotlin tests. See the
[multi-language setup](docs/monorepo.md) and its
[workflow example](examples/monorepo/kotlin.yml).

The [issue #1 case study](docs/case-studies/issue-1/README.md) records how the
Hive Mind guide was applied to Kotlin and the first-user adoption plan.
