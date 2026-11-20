#!/usr/bin/env bash

set -euo pipefail
# Fail on every known advisory regardless of severity. Read committed locks
# and verification metadata without executing or re-resolving Gradle code.
lockfiles=()
while IFS= read -r -d '' path; do
    case ${path##*/} in
        gradle.lockfile|buildscript-gradle.lockfile|verification-metadata.xml|package-lock.json)
            lockfiles+=(--lockfile "$path")
            ;;
    esac
done < <(git ls-files -z -- .)
if [[ ${#lockfiles[@]} == 0 ]]; then
    echo '::error::Commit Gradle dependency locks or verification metadata before enabling the audit.'
    exit 1
fi
osv-scanner scan source "${lockfiles[@]}"
