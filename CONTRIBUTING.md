# Contributing

Use the Gradle Wrapper and a topic branch. Run the fast checks in the
[README](README.md#quick-start), then the target tests affected by the change.
Use `./gradlew ktlintFormat` to fix formatting before staging a commit.

Install [Gitleaks](https://github.com/gitleaks/gitleaks/releases) and enable the
hook with `git config core.hooksPath .githooks`. The hook scans staged changes
for credentials and checks size, formatting, lint and compilation locally.
Linux amd64 users can install the CI pin with
`bash scripts/install-ci-tool.sh gitleaks ~/.local/bin`.

For a dependency update, review the new artifact origins and verification
checksums before committing regenerated metadata and locks:

```sh
./gradlew dependencies --write-locks --write-verification-metadata sha256
./gradlew kotlinUpgradePackageLock jvmTest jsNodeTest
```

If a dependency was removed or superseded, prune stale components from
`gradle/verification-metadata.xml` after confirming that no supported build
uses them. CI scans that file as well as the resolution locks. Run
`bash scripts/audit-dependencies.sh` with OSV-Scanner on your path to repeat CI's
audit. Upgrade the JavaScript runtime when changing Kotlin's npm tooling if the
updated packages require it.

For a Kotlin, Gradle or Docker change, add a new
[changeset](.changeset/README.md). CI updates the version in
`gradle.properties` after merge. For changes to the pipeline itself run
`python3 -m unittest discover -s tests -v` before pushing.
