# Issue 1 case study

## Baseline and scope

The issue, opened on 2026-11-20, called for the Hive Mind CI/CD practices in a
reusable Kotlin template and named Hive Mind and UI as the first adopters.
The original `main` commit, `be96a23`, had a short README, license and
ignore rules. PR #2 opened with only a placeholder file. There were no issue
comments, sub-issues, PR conversations, inline review comments or reviews when
work began. The absence of a build, pipeline and release process meant that
adopters would have to invent these controls independently. [Issue 1](https://github.com/link-foundation/kotlin-ai-driven-development-pipeline-template/issues/1), [PR 2](https://github.com/link-foundation/kotlin-ai-driven-development-pipeline-template/pull/2), [source captures](sources/).

The pinned Hive Mind guide defines 17 practices and a language-to-template
catalog. Hive Mind added the C/C++ entry to both remediation detection and its
localized documentation in PR #2574. The sibling Java template's PR #25
demonstrated why auditing declared coordinates alone misses tooling
dependencies. UI's merged Kotlin parser and Compose renderer use separate
Gradle builds and shared parser, document and token fixtures. Its current
Kotlin workflow also has Android and iOS jobs. The pilot should preserve that
coverage when introducing one `./kotlin` entry point. [Hive Mind guide](https://github.com/link-assistant/hive-mind/blob/0f07c025bdf67f7391c7d5c47baf9ffca6fed1c9/docs/CI-CD-BEST-PRACTICES.md), [remediation precedent](https://github.com/link-assistant/hive-mind/pull/2574), [Java audit](https://github.com/link-foundation/java-ai-driven-development-pipeline-template/pull/25), [UI Kotlin workflow](https://github.com/link-foundation/ui/blob/5a7de318166319a0847c9a339fe836c8843b4588/.github/workflows/kotlin.yml), [UI Kotlin parser](https://github.com/link-foundation/ui/pull/89), [UI Compose renderer](https://github.com/link-foundation/ui/pull/106).

## Requirements and verification plan

| Requirement | Implementation | Verification |
| --- | --- | --- |
| Provide a useful Kotlin template | Gradle Wrapper, Kotlin Multiplatform sample, tests, publication metadata and an executable JVM example | Run the wrapper, both target suites, local Maven staging and the example. |
| Implement the same or similar ideas as the Hive Mind guide | Map all 17 practices to Kotlin controls in the table below | Check the workflow and its policy tests on the PR head. |
| Support a multi-language pilot at UI's `./kotlin` | Read-only workflow with project directory, shared paths and target tasks as inputs | Test scoped and shared-path routing, then ask UI to adopt it with its existing target matrix. |
| Report to Hive Mind once ready | Request a Kotlin entry in the docs, translations and remediation mapping | Record the issue URL and the desired catalog acceptance checks. |
| Report to UI once ready | Request a coordinating `./kotlin` build and workflow with preserved targets and fixtures | Record the issue URL and pilot acceptance checks. |
| Compile issue and research data under `docs/case-studies/issue-1` | Preserve public starting artifacts, external sources, decisions and evidence in this directory | Inspect the captures and run documentation link checks. |
| Deliver in a single PR | PR #2 contains code, docs, evidence and a closing reference to issue #1 | Verify the PR head, diff and hosted checks. |

## Translating the 17 practices

| Practice | Alternative considered | Selected implementation and check |
| --- | --- | --- |
| 1. Relevant paths | Workflow-level GitHub path filters | Classify the actual Git diff and keep an unconditional terminal status. Test docs-only, deletion and nested shared inputs. |
| 2. File limits | Detekt source rules alone | One tracked-file check for 1,500-line code and 2,500-line Markdown, usable in CI and the hook. |
| 3. Formatting | Spotless wrapping ktlint | Use the ktlint Gradle plugin and Kotlin official style. Run `ktlintCheck`; offer `ktlintFormat` locally. |
| 4. Static analysis | Compiler warnings alone | Run Detekt, compiler warnings as errors and explicit API checks. |
| 5. Fast-fail | One full Gradle invocation per job | Gate target tests on lint, compilation, workflow, docs and audit checks. Gate Docker smoke tests on target tests. |
| 6. Changesets | Release Please commit conventions | Validate one newly added per-change SemVer fragment for production paths. Test highest bump and docs exemption. |
| 7. Actual merge result | GitHub's original merge preview | Capture the current base during planning and merge it into all relevant jobs. Test an advancing base and configure strict required checks or queue. |
| 8. Local hooks | Python pre-commit framework | Use a Git hook backed by the same Gradle and file checks. Scan staged Git changes with Gitleaks. |
| 9. Release automation | Release PR or GitHub Packages | Atomically push version commit and tag, generate a checksummed GitHub release by default, and optionally publish signed Maven Central artifacts. Exercise local Maven and release retries. |
| 10. Concurrency | One cancellable workflow group | Cancel each superseded reader independently. Serialize writers and recompute metadata after a genuine non-fast-forward. |
| 11. Secrets | Hosted push protection only | Scan incoming history in CI and staged changes in the local hook, with redaction. |
| 12. Documentation | Online link checks on every commit | Gate size, sections and relative links in the PR. Check live external links on a schedule. |
| 13. Native containers | Build both architectures through QEMU | Build and smoke-test on both GitHub native runners with per-arch caches; assemble and anonymously verify a GHCR manifest after core release. |
| 14. Workflow linting | YAML syntax alone | Run containerized actionlint with ShellCheck and zizmor with annotations and a confidence floor. |
| 15. Full dependency audit | Dependency review only | Scan committed Gradle locks, verification metadata and Kotlin/JS npm locks for all known advisories. Run on changes and on a schedule. |
| 16. Publishing preflight | Check only for non-empty secrets | Probe staged Central upload and signing, plus GHCR blob write/cancel before expensive publishing builds. Forks run local publications. |
| 17. Changed external state | Block every PR on version freshness | Use Dependabot for updates and a scheduled stale-PR check. Keep strict vulnerability results, retry observations of transient registry states and report skipped work. |

## Tooling decisions and data

- **Gradle and Kotlin.** Maven is an option for Kotlin/JVM, but Gradle Kotlin DSL
  provides source sets, native and web target hooks, and publications for both
  the common component and each target. Kotlin 2.4.21 and Gradle 9.7.0 are a
  supported combination. The wrapper checksum guards the distribution, Gradle
  strict locks guard selected versions, and verification metadata covers
  build-tool artifacts the application lock omits. [Kotlin compatibility](https://kotlinlang.org/docs/multiplatform/multiplatform-compatibility-guide.html), [Kotlin publication](https://kotlinlang.org/docs/multiplatform/multiplatform-publish-lib-setup.html), [Gradle locks](https://docs.gradle.org/current/userguide/dependency_locking.html), [Gradle checksums](https://docs.gradle.org/current/userguide/gradle_wrapper.html).
- **Formatting and analysis.** The standalone ktlint CLI, Spotless and native
  ktlint plugin all support Kotlin formatting. The native plugin includes Kotlin
  source sets and Gradle scripts. Detekt adds Kotlin-specific static analysis.
  The 2.x line is pre-release, so the template pins and tests the exact version;
  its default syntax rules run independently of the Kotlin compiler version.
  [ktlint plugin](https://github.com/JLLeitschuh/ktlint-gradle), [Detekt compatibility](https://github.com/detekt/detekt#requirements).
- **Audit evidence.** The first passing build used Kotlin 2.3.21 and Gradle
  9.3.0. The baseline scan found advisories across the Kotlin plugin, build-time
  Logback and Bouncy Castle, and npm test tooling. A version upgrade and
  targeted build-tool resolution overrides brought the three committed inputs
  to zero reported advisories on 2026-11-20. The dependency audit supported
  Maven, Gradle verification entries and npm in the same scanner. [OSV input formats](https://google.github.io/osv-scanner/supported-languages-and-lockfiles/), [scan inventory](sources/dependency-audit.md).
- **Publication.** GitHub Releases provide an out-of-the-box file distribution
  with the repository token. Maven Central offers consumer coordinates and
  signed artifacts after namespace and token setup. JReleaser and GradleUp's
  NMCP can upload Gradle publications. Using the Portal API directly keeps the
  deployment ID on the GitHub draft and lets the workflow resume that
  deployment across runner restarts. Anonymous checks observe the published
  coordinates. [Portal API](https://central.sonatype.org/publish/publish-portal-api/), [Gradle integrations](https://central.sonatype.org/publish/publish-portal-gradle/), [Central namespaces](https://central.sonatype.org/register/namespace/).
- **Container releases.** The staged JVM bytecode and dependencies are
  architecture-independent. Native amd64 and arm64 runners can verify both
  platform images against the same runtime bytes without recompiling Kotlin in
  Docker. GHCR is an optional mirror with public visibility controlled by its
  package settings. [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), [GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

## Verification and adoption

- The hosted pipeline passed release preview, workflow linting, JVM and JS
  tests, Maven staging, documentation and dependency checks, and native
  amd64 and arm64 smoke tests. The first clean-runner attempts exposed two
  official plugin-marker POMs with different hashes on the Gradle Plugin
  Portal and Maven Central; both sources were checked and pinned. The PR
  carries the checks for the final revision. [Hosted run](https://github.com/link-foundation/kotlin-ai-driven-development-pipeline-template/actions/runs/44697437139), [template PR](https://github.com/link-foundation/kotlin-ai-driven-development-pipeline-template/pull/2).
- The pipeline regression suite exercises Kotlin path selection, release
  metadata pushes and crash recovery in local Git repositories. The separate
  signing experiment builds and verifies the common, JVM and JS publications
  with a fresh disposable PGP key. [Regression suite](../../../tests/test_pipeline.py), [signing experiment](../../../experiments/verify-signed-bundle.sh).
- The adoption reports request updates to the Hive Mind documentation and
  language detection, and a UI pilot that preserves its existing target and
  shared-fixture coverage from `./kotlin`. [Hive Mind issue #4098](https://github.com/link-assistant/hive-mind/issues/4098), [UI issue #265](https://github.com/link-foundation/ui/issues/265).
- The live GitHub Release requires a run from `main`. The external mirrors
  require a registered Central namespace and publisher credentials or a GHCR
  package with public visibility. The pull request verifies the release plan
  and local artifacts. [Release setup and recovery](../../releases.md).
