# Release setup and recovery

## Default GitHub release

A copied template can create GitHub Releases using the job's short-lived
`GITHUB_TOKEN`. Replace the sample coordinates and POM metadata before releasing.
Allow Actions to write contents and, if a branch or tag rule rejects the metadata
push, permit the release actor to update those refs. The workflow fails with
the remote rule error. It never force-pushes.

Publish mode is available only for `main`. Pull requests from forks exercise
the same Gradle publication tasks against a temporary local Maven repository
without registry credentials. The writer checks that the latest remote tree
still matches the one validated by CI. If another metadata writer wins, it
fetches and computes the version again. If source changed, the newer run must
qualify the new tree. The GitHub release includes a portable Maven repository
and JVM archives with SHA-256 checksums.

## Maven Central

Register the namespace, set the POM metadata, and create the following GitHub
Actions secrets. Enable the repository variable `PUBLISH_CENTRAL=true` before
the first release you want to publish:

- `CENTRAL_USERNAME` and `CENTRAL_PASSWORD` contain the Central Portal user token.
- `SIGNING_KEY` contains an ASCII-armored PGP private key.
- `SIGNING_PASSWORD` contains its passphrase when applicable.

The preflight uses a disposable, user-managed staging upload and verifies that
the key can sign. The actual deployment validates namespace ownership and
artifact signatures. The template uses Central's documented Portal token API
and keeps credentials out of fork checks. The writer holds a draft GitHub
release while publishing to Central and verifies the common, JVM and JS
coordinates anonymously before publishing the GitHub draft.

A failed release can be dispatched again from `main` with `operation=release`.
The writer first repairs missing artifacts for the recorded version before
consuming more changesets. Central's deployment ID is saved on the draft, and
recovery polls the ID and public artifacts. If the worker lost the upload
response, check Central Portal for the deployment named
`OWNER/REPO-vMAJOR.MINOR.PATCH`. Upload its ID in `central-deployment.txt` to
the draft. If Central confirms there was no deployment, delete
`central-upload-attempt.txt` from the draft to allow a fresh upload.
If Central rejected a deployment, inspect it in the Portal and resolve the
validation failure before retrying. Releases already public on Central are
immutable.

## GitHub Container Registry

Enable `PUBLISH_GHCR=true` if the project ships its JVM container. The package
needs Actions access to publish from this repository and public visibility for
anonymous pulls. On a new package, change its visibility in package settings
after the first push. The final verification job reports when public access is
missing. A manual release dispatch verifies the existing image again.

The image workflow probes permissions with an open-and-cancel blob upload,
builds and smoke-tests both architectures on native runners, and uses BuildKit
caching per architecture. With the GitHub Release already public, a serialized
writer pushes the images, assembles a manifest from their digests, and leaves a
separate anonymous verification job to inspect the resulting platform list.

For other release tooling, share the `main-writer-OWNER/REPO-main` concurrency
group. A failed optional GHCR mirror leaves the core release available and can
be recovered on another dispatch.
