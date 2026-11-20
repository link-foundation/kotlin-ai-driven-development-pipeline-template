# Dependency audit summary

Collected 2026-11-20 with OSV-Scanner 2.7.1 from committed-format inputs.
The reproduced inputs were the Gradle resolution lock, Gradle verification
metadata and Kotlin/JS package lock.

| Build | Gradle lock records | Verification metadata records | npm lock records | Advisory IDs |
| --- | ---: | ---: | ---: | ---: |
| Kotlin 2.3.21 / Gradle 9.3.0 | 109 | 139 | 84 | 14 |
| Kotlin 2.4.21 / Gradle 9.7.0 | 132 | 158 | 64 | 0 |

The baseline records included `kotlin-gradle-plugin`, `logback-core`,
`bcpg-jdk18on`, `bcpkix-jdk18on`, `bcprov-jdk18on`, `diff`, `glob`,
`minimatch`, and `serialize-javascript`. The updated build resolved newer
versions of the affected components and still passed both target suites.
To repeat the final scan, install OSV-Scanner and run
`bash scripts/audit-dependencies.sh` from the repository root.
