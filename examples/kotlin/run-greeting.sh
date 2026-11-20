#!/usr/bin/env bash
# Use the example library's JVM entry point from the staged distribution.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
./gradlew --console=plain stageRuntime
java -cp 'build/runtime/*' template.MainKt "$@"
