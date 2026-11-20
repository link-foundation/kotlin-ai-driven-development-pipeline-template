#!/usr/bin/env bash
# Exercise the actual Gradle signing tasks with a disposable local key.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
keyring=$(mktemp -d)
trap 'gpgconf --homedir "$keyring" --kill gpg-agent; rm -rf "$keyring"' EXIT
chmod 700 "$keyring"
gpg --homedir "$keyring" --batch --pinentry-mode loopback --passphrase '' \
  --quick-generate-key 'Template verification <pipeline@example.invalid>' rsa2048 sign 1d
SIGNING_KEY=$(gpg --homedir "$keyring" --armor --export-secret-keys)
export SIGNING_KEY
PYTHONPATH=scripts python3 -c 'from registries import check_signing; check_signing()'
./gradlew --no-daemon --console=plain publishAllPublicationsToBundleRepository
for suffix in '' -jvm -js; do
    name="kotlin-pipeline-example$suffix"
    pom="build/maven-bundle/io/github/link-foundation/$name/0.0.0/$name-0.0.0.pom"
    gpg --homedir "$keyring" --verify "$pom.asc" "$pom"
done
