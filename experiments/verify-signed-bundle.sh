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
PYTHONPATH=scripts python3 - "$keyring" <<'PY'
from pathlib import Path
import sys
from zipfile import ZipFile

from release import PROPERTIES, archive, stage_central_bundle, version

scratch = Path(sys.argv[1])
release_version = ".".join(map(str, version(PROPERTIES.read_text(encoding="utf-8"))))
repository = scratch / "repository.zip"
bundle = scratch / "central-bundle.zip"
archive(Path("build/maven-bundle"), repository)
stage_central_bundle(repository, bundle, release_version)
with ZipFile(bundle) as publication:
    publication.extractall(scratch / "bundle")
PY
while IFS= read -r -d '' pom; do
    gpg --homedir "$keyring" --verify "$pom.asc" "$pom"
done < <(find "$keyring/bundle" -type f -name '*.pom' -print0)
