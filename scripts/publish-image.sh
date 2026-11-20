#!/usr/bin/env bash

set -euo pipefail
tag=${1:?Expected a version tag}
if [[ ! $tag =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo 'Expected a release tag matching vMAJOR.MINOR.PATCH.' >&2
    exit 1
fi

# Recheck under the same writer lock. A prior run may have published while
# this job was waiting for native builds.
status=$(python3 scripts/release.py image-preflight --tag "$tag")
if [[ $status == *needed=false* ]]; then
    printf '%s\n' "$status"
    exit 0
fi
image="ghcr.io/${GITHUB_REPOSITORY,,}"
digests=()
for arch in amd64 arm64; do
    docker load --input "build/images/kotlin-image-$arch/image.tar"
    docker tag "kotlin-pipeline:release-$arch" "$image:$tag-$arch"
    log=$(docker push "$image:$tag-$arch")
    printf '%s\n' "$log"
    digest=$(awk '/digest: sha256:/ { for (i=1;i<NF;i++) if ($i=="digest:") print $(i+1) }' <<< "$log")
    if [[ ! $digest =~ ^sha256:[0-9a-f]{64}$ ]]; then
        echo "::error::Push for $arch did not return an image digest."
        exit 1
    fi
    digests+=("$image@$digest")
done
docker buildx imagetools create --tag "$image:$tag" "${digests[@]}"
