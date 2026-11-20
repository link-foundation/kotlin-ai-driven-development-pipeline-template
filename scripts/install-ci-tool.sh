#!/usr/bin/env bash
# Install immutable, checksum-pinned Linux x64 tool binaries on hosted runners.
set -euo pipefail

case ${1:-} in
  gitleaks)
    repo=gitleaks/gitleaks
    tag=v8.30.1
    asset=gitleaks_8.30.1_linux_x64.tar.gz
    sha=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb
    ;;
  osv-scanner)
    repo=google/osv-scanner
    tag=v2.7.1
    asset=osv-scanner_linux_amd64
    sha=fb7dab19a8bd9bbe5c3189f09d4b7ee1820c9553a23bac202648a56efd2f6ee8
    ;;
  *)
    echo "Usage: $0 {gitleaks|osv-scanner}" >&2
    exit 2
    ;;
esac
destination=${2:-${RUNNER_TEMP:?Set RUNNER_TEMP or pass an installation directory}/bin}
mkdir -p "$destination"
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
curl --fail --silent --show-error --location --retry 3 --max-time 60 \
  "https://github.com/$repo/releases/download/$tag/$asset" -o "$scratch/$asset"
printf '%s  %s\n' "$sha" "$scratch/$asset" | sha256sum --check
if [[ $asset == *.tar.gz ]]; then
  tar -xzf "$scratch/$asset" -C "$scratch" "$1"
  asset=$1
fi
install -m 755 "$scratch/$asset" "$destination/$1"
if [[ -n ${GITHUB_PATH:-} ]]; then
  printf '%s\n' "$destination" >> "$GITHUB_PATH"
fi
