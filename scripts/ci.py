#!/usr/bin/env python3
"""Shared local and GitHub Actions checks for a Gradle project."""

import argparse
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


VERSION = re.compile(r"^version=(\d+)\.(\d+)\.(\d+)$", re.MULTILINE)
BUMP = re.compile(r"\A---\nbump: (patch|minor|major)\n---\n+(.+)\Z", re.DOTALL)
CODE_SUFFIXES = {".kt", ".kts", ".java", ".gradle", ".groovy", ".py", ".sh", ".bat", ".yml", ".yaml"}
BUILD_FILES = {
    "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
    "gradle.properties", "gradlew", "gradlew.bat", "gradle.lockfile",
}


def git(*args, check=True):
    return subprocess.run(("git", *args), check=check, capture_output=True)


def project_path(value):
    project = PurePosixPath(value)
    if project.is_absolute() or ".." in project.parts or any(c in value for c in "\n\r\\"):
        raise ValueError(f"Expected a repository-relative directory, got {value!r}")
    root = Path.cwd()
    if not Path(project).resolve().is_relative_to(root):
        raise ValueError("Project directory must resolve inside the repository")
    return project


def outputs(**values):
    for key, value in values.items():
        value = str(value).lower() if isinstance(value, bool) else value
        line = f"{key}={value}"
        print(line)
        if output_file := os.environ.get("GITHUB_OUTPUT"):
            with open(output_file, "a", encoding="utf-8") as output:
                print(line, file=output)


def compare(project, paths, additional_paths):
    flags = dict(kotlin=False, docs=False, container=False, workflow=False, production=False)
    additional = [project_path(line.strip()) for line in additional_paths.splitlines() if line.strip()]
    for name in paths:
        path = PurePosixPath(name)
        if path.parts[:1] == (".github",):
            flags["workflow"] = True
        if any(path.is_relative_to(item) for item in additional):
            flags["kotlin"] = True
        if not path.is_relative_to(project):
            continue
        relative = path.relative_to(project)
        top = relative.parts[0]
        if top in {".github", ".changeset", "experiments", "data"} or path.name == ".gitkeep":
            continue
        if path.suffix.lower() == ".md" or top == "docs":
            flags["docs"] = True
            continue
        if top in {"Dockerfile", ".dockerignore", "docker"}:
            flags["container"] = True
            flags["production"] = True
            continue
        flags["kotlin"] = True
        if top in {"src", "gradle", "buildSrc", "build-logic"} or path.name in BUILD_FILES:
            flags["production"] = True
    return flags


def merge_base(base):
    if not re.fullmatch(r"[0-9a-f]{40}", base):
        raise ValueError("Expected a full Git commit SHA")
    result = git(
        "-c", "user.name=github-actions[bot]",
        "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "merge", "--no-edit", base, check=False,
    )
    if result.returncode:
        sys.stderr.buffer.write(result.stdout + result.stderr)
        raise ValueError("Could not merge the current base. Merge it into the pull request and resolve conflicts.")


def diff_names(base, *options):
    data = git("diff", "--no-renames", "--name-only", "-z", *options, base, "HEAD").stdout
    return [os.fsdecode(path) for path in data.split(b"\0") if path]


def version(contents):
    matches = list(VERSION.finditer(contents))
    if len(matches) != 1:
        raise ValueError("gradle.properties must have one version=MAJOR.MINOR.PATCH line")
    return tuple(map(int, matches[0].groups()))


def read_changeset(path):
    match = BUMP.fullmatch(path.read_text(encoding="utf-8"))
    if not match or not match[2].strip() or not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.md", path.name):
        raise ValueError(f"Invalid changeset {path}. See .changeset/README.md.")
    return match[1], match[2].strip()


def check_metadata(project, base, production, gradle_versioning):
    if not gradle_versioning:
        return
    properties = project / "gradle.properties"
    current = version(Path(properties).read_text(encoding="utf-8"))
    old = git("show", f"{base}:{properties}", check=False)
    if old.returncode == 0 and version(old.stdout.decode()) != current:
        raise ValueError(f"Only the release workflow may change version in {properties}")
    changesets = project / ".changeset"
    additions = []
    for name in diff_names(base, "--diff-filter=AM"):
        fragment = PurePosixPath(name)
        if fragment.parent == changesets and fragment.suffix == ".md" and fragment.name != "README.md":
            read_changeset(Path(name))
            additions.append(name)
    new_paths = set(diff_names(base, "--diff-filter=A"))
    if production and not new_paths.intersection(additions):
        raise ValueError(f"Production changes require a new release note under {changesets}/")


def plan(args):
    project = project_path(args.project)
    event = os.environ["EVENT_NAME"]
    base = os.environ.get("BEFORE_SHA", "")
    if event == "pull_request":
        ref = os.environ["BASE_REF"]
        base = git("rev-parse", "--verify", f"refs/remotes/origin/{ref}").stdout.decode().strip()
        merge_base(base)
    if event != "pull_request" and (
        event != "push" or not base or not any(c != "0" for c in base)
        or git("cat-file", "-e", f"{base}^{{commit}}", check=False).returncode
    ):
        flags = dict(kotlin=True, docs=True, container=True, workflow=True, production=True)
        base = ""
        if event == "push":
            print("::notice::No comparable previous commit. Running all checks.")
    else:
        flags = compare(project, diff_names(base), args.additional_paths)
    if event == "pull_request":
        check_metadata(project, base, flags["production"], args.versioning)
    merged = base if event == "pull_request" else ""
    if not any(flags.values()):
        print("::notice::No changes in this Gradle project or its configured shared inputs.")
    outputs(**flags, merge_base=merged)


def check_files(args):
    project = project_path(args.project)
    raw = git("ls-files", "-z", "--", str(project)).stdout
    errors = []
    for name in map(os.fsdecode, raw.split(b"\0")):
        path = Path(name)
        if not name or not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(project)
        if relative.parts[0] in {"data", "experiments"}:
            continue
        if path.suffix.lower() == ".md":
            limit = 2500
        elif path.suffix.lower() in CODE_SUFFIXES or path.name in {"Dockerfile", "gradlew"}:
            limit = 1500
        else:
            continue
        count = len(path.read_bytes().splitlines())
        if count > limit:
            errors.append(f"{path} has {count} lines (limit {limit})")
    if args.docs:
        headings = ("## Quick start", "## CI checks", "## Releases", "## Multi-language repositories")
        readme = Path(project / "README.md").read_text(encoding="utf-8").splitlines()
        errors.extend(f"README.md is missing {heading}" for heading in headings if heading not in readme)
    if errors:
        raise ValueError("\n".join(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("--project", default=".")
    plan_parser.add_argument("--additional-paths", default="")
    plan_parser.add_argument("--versioning", action="store_true")
    merge_parser = commands.add_parser("merge")
    merge_parser.add_argument("base", nargs="?", default="")
    file_parser = commands.add_parser("files")
    file_parser.add_argument("--project", default=".")
    file_parser.add_argument("--docs", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "plan":
            plan(args)
        elif args.command == "merge" and args.base:
            merge_base(args.base)
        elif args.command == "files":
            check_files(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
