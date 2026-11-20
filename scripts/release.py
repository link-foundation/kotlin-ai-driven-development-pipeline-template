#!/usr/bin/env python3
"""Plan, commit and recover a release from a tested default-branch commit."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from ci import VERSION, git, outputs, read_changeset, version
import registries

PROPERTIES = Path("gradle.properties")
CHANGELOG = Path("CHANGELOG.md")
FRAGMENTS = Path(".changeset")
BUNDLE = "maven-bundle.zip"
RUNTIME = "jvm-runtime.zip"
CHECKSUMS = "SHA256SUMS"
CENTRAL_ID = "central-deployment.txt"
CENTRAL_ATTEMPT = "central-upload-attempt.txt"


def pending():
    return sorted(path for path in FRAGMENTS.glob("*.md") if path.name != "README.md")


def next_release(current, fragments):
    ranks = {"major": 0, "minor": 1, "patch": 2}
    notes = [read_changeset(path) for path in fragments]
    index = min(ranks[bump] for bump, _ in notes)
    result = (*current[:index], current[index] + 1, *((0,) * (2 - index)))
    return ".".join(map(str, result)), "\n\n".join(note for _, note in notes)


def update_metadata(new_version, notes, fragments):
    original = PROPERTIES.read_text(encoding="utf-8")
    PROPERTIES.write_text(VERSION.sub(f"version={new_version}", original), encoding="utf-8")
    title, _, history = CHANGELOG.read_text(encoding="utf-8").partition("\n")
    CHANGELOG.write_text(
        f"{title}\n\n## {new_version}\n\n{notes}\n\n{history.lstrip()}",
        encoding="utf-8",
    )
    for path in fragments:
        path.unlink()


def command(*args, env=None):
    subprocess.run(args, check=True, env=env)


def git_text(*args):
    return git(*args).stdout.decode().strip()


def gh_release(tag):
    root = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/releases"
    headers = {"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"}
    response = registries.request(f"{root}/tags/{tag}", headers=headers)
    if response[0] != 404:
        return json.loads(registries.require(response, {200}, f"GitHub release lookup for {tag}"))
    # The tag endpoint only promises published releases. Recover drafts
    # through the paginated release inventory visible to the writer.
    page = 1
    while True:
        response = registries.request(f"{root}?per_page=100&page={page}", headers=headers)
        releases = json.loads(registries.require(response, {200}, "List GitHub releases"))
        draft = next((item for item in releases if item["tag_name"] == tag), None)
        if draft or len(releases) < 100:
            return draft or {}
        page += 1


def asset_names(release):
    return {asset["name"] for asset in release.get("assets", [])}


def coordinates():
    contents = PROPERTIES.read_text(encoding="utf-8")
    group, = re.findall(r"^group=([a-zA-Z0-9_.-]+)$", contents, re.MULTILINE)
    artifact, = re.findall(r'^rootProject\.name = "([a-zA-Z0-9_.-]+)"$', Path("settings.gradle.kts").read_text(),
                          re.MULTILINE)
    return group, artifact


def package_urls(release_version):
    group, artifact = coordinates()
    return [registries.central_pom(group, artifact + suffix, release_version) for suffix in ("", "-jvm", "-js")]


def central_enabled():
    return os.environ.get("PUBLISH_CENTRAL") == "true"


def needs_recovery(release_version):
    if release_version == "0.0.0":
        return False
    release = gh_release(f"v{release_version}")
    missing = release.get("draft", False) or not {BUNDLE, RUNTIME, CHECKSUMS} <= asset_names(release)
    return missing or (central_enabled() and not all(map(registries.public_status, package_urls(release_version))))


def archive(directory, archive_path):
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as output:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(directory))
    if not output.namelist() or archive_path.stat().st_size > registries.ZIP_LIMIT:
        raise RuntimeError(f"{archive_path.name} is empty or exceeds the 50 MiB release size budget")


def build_assets(target, release_version, folder):
    import hashlib

    env = os.environ.copy()
    for name in ("GH_TOKEN", "CENTRAL_USERNAME", "CENTRAL_PASSWORD"):
        env.pop(name, None)
    if not central_enabled():
        env.pop("SIGNING_KEY", None)
        env.pop("SIGNING_PASSWORD", None)
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / "source"
        git("worktree", "add", "--detach", str(source), target)
        try:
            command(str(source / "gradlew"), "-p", str(source), "--no-daemon", "--console=plain",
                    "publishAllPublicationsToBundleRepository", "stageRuntime", env=env)
            repository = source / "build" / "maven-bundle"
            if central_enabled() and not list(repository.rglob(f"*-{release_version}.pom.asc")):
                raise RuntimeError("Gradle did not sign the publication")
            archive(repository, folder / BUNDLE)
            archive(source / "build" / "runtime", folder / RUNTIME)
        finally:
            git("worktree", "remove", "--force", str(source))
    with (folder / CHECKSUMS).open("w", encoding="utf-8") as output:
        for name in (BUNDLE, RUNTIME):
            with (folder / name).open("rb") as file:
                print(f"{hashlib.file_digest(file, 'sha256').hexdigest()}  {name}", file=output)


def push(branch, tag):
    refs = [f"HEAD:refs/heads/{branch}", f"HEAD:refs/tags/{tag}"]
    result = git("push", "--atomic", "origin", *refs, check=False)
    if result.returncode == 0:
        print(result.stderr.decode().strip())
        return True
    message = (result.stdout + result.stderr).decode(errors="replace")
    print(message.rstrip(), file=sys.stderr)
    if any(code in message for code in ("GH006", "GH013", "protected branch", "repository rule")):
        raise RuntimeError("Allow github-actions[bot] to push release metadata in the applicable branch/tag rule.")
    if any(reason in message for reason in ("non-fast-forward", "fetch first", "stale info", "already exists")):
        return False
    raise RuntimeError("Git push failed. See the remote error above.")


def validated_tree_matches(old, new):
    ignored = (":(exclude)gradle.properties", ":(exclude)CHANGELOG.md", ":(exclude).changeset")
    if git("diff", "--quiet", old, new, "--", ".", *ignored, check=False).returncode != 0:
        return False
    return (
        VERSION.sub("", git_text("show", f"{old}:{PROPERTIES}"))
        == VERSION.sub("", git_text("show", f"{new}:{PROPERTIES}"))
    )


def verify_metadata_commit(parent, commit):
    actual = git("diff", "--name-status", "-z", "--no-renames", parent, commit).stdout.decode().split("\0")
    for status, name in zip(actual[0::2], actual[1::2]):
        if not (name in {str(PROPERTIES), str(CHANGELOG)} and status == "M"
                or Path(name).parent == FRAGMENTS and status == "D" and name != ".changeset/README.md"):
            raise RuntimeError(f"Refusing to push unexpected {status} {name}")
    if not validated_tree_matches(parent, commit):
        raise RuntimeError("The release commit modifies files beyond release metadata")


def release_notes(target, release_version):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as output:
        lines = git_text("show", f"{target}:{CHANGELOG}").splitlines()
        start = lines.index(f"## {release_version}") + 1
        end = next((index for index in range(start, len(lines)) if lines[index].startswith("## ")), len(lines))
        output.write("\n".join(lines[start:end]).strip() + "\n")
        return Path(output.name)


def ensure_github_release(tag, target, folder):
    release_version = tag[1:]
    release = gh_release(tag)
    names = {BUNDLE, RUNTIME, CHECKSUMS}
    if names - asset_names(release):
        build_assets(target, release_version, folder)
        if release:
            # GitHub stores immutable release bytes. If a draft only has some
            # assets, keep its bundle/checksum pair intact by rebuilding the draft.
            if asset_names(release).intersection(names):
                if not release["draft"]:
                    raise RuntimeError(f"{tag} has an incomplete published asset set. Restore the missing assets.")
                for name in sorted(asset_names(release).intersection(names)):
                    command("gh", "release", "delete-asset", tag, name, "--yes")
            command("gh", "release", "upload", tag, *(str(folder / name) for name in sorted(names)))
        else:
            notes = release_notes(target, release_version)
            try:
                command("gh", "release", "create", tag, "--verify-tag", "--draft", "--title", tag,
                        "--notes-file", str(notes), *(str(folder / name) for name in sorted(names)))
            finally:
                notes.unlink()
    existing = gh_release(tag)
    if names - asset_names(existing):
        raise RuntimeError(f"GitHub has not confirmed release {tag} with all required assets")


def ensure_central(tag, folder):
    urls = package_urls(tag[1:])
    if all(map(registries.public_status, urls)):
        print(f"Maven Central already serves {tag}.")
        return
    assets = asset_names(gh_release(tag))
    if CENTRAL_ID in assets:
        command("gh", "release", "download", tag, "--pattern", CENTRAL_ID, "--dir", str(folder))
        deployment = (folder / CENTRAL_ID).read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", deployment):
            raise RuntimeError(f"Invalid Central deployment ID on {tag}")
    else:
        if CENTRAL_ATTEMPT in assets:
            raise RuntimeError(
                f"{tag} has an unconfirmed upload. In Central Portal, find the deployment named "
                f"{os.environ['GITHUB_REPOSITORY']}-{tag} and attach its ID as {CENTRAL_ID}, "
                f"or remove {CENTRAL_ATTEMPT} after confirming there was no deployment."
            )
        if not (folder / BUNDLE).exists():
            command("gh", "release", "download", tag, "--pattern", BUNDLE, "--dir", str(folder))
        attempt = folder / CENTRAL_ATTEMPT
        attempt.write_text(f"Attempted by {os.environ.get('GITHUB_RUN_ID', 'local run')}\n", encoding="utf-8")
        command("gh", "release", "upload", tag, str(attempt))
        deployment = registries.upload_to_central(folder / BUNDLE, f"{os.environ['GITHUB_REPOSITORY']}-{tag}")
        print(f"Central accepted deployment {deployment}")
        receipt = folder / CENTRAL_ID
        receipt.write_text(deployment + "\n", encoding="utf-8")
        command("gh", "release", "upload", tag, str(receipt))
    registries.wait_for(lambda: registries.activate_deployment(deployment), "Central deployment approval")
    registries.wait_for(lambda: all(map(registries.public_status, urls)), f"Public Maven artifacts for {tag}")


def complete(tag, target, runtime):
    with tempfile.TemporaryDirectory() as scratch:
        folder = Path(scratch)
        ensure_github_release(tag, target, folder)
        if central_enabled():
            ensure_central(tag, folder)
        if gh_release(tag).get("draft", False):
            command("gh", "release", "edit", tag, "--draft=false")
        if gh_release(tag).get("draft", True):
            raise RuntimeError(f"GitHub did not confirm publication of {tag}")
        print(f"GitHub release {tag} exists with all required assets.")
        if runtime:
            if not (folder / RUNTIME).is_file():
                command("gh", "release", "download", tag, "--pattern", RUNTIME, "--dir", scratch)
            shutil.copyfile(folder / RUNTIME, runtime)


def run_release(branch, runtime):
    validated = git_text("rev-parse", "HEAD")
    for attempt in range(1, 4):
        remote = f"refs/remotes/origin/{branch}"
        git("fetch", "origin", f"refs/heads/{branch}:{remote}", "--tags")
        tip = git_text("rev-parse", remote)
        if git("merge-base", "--is-ancestor", validated, tip, check=False).returncode != 0:
            raise RuntimeError("The validated commit is no longer on the default branch")
        if not validated_tree_matches(validated, tip):
            print("::notice::A newer source tree superseded this release run. Its own CI must qualify it.")
            outputs(tag="")
            return
        git("reset", "--hard", tip)
        current = version(PROPERTIES.read_text(encoding="utf-8"))
        current_string = ".".join(map(str, current))
        if needs_recovery(current_string):
            old_tag = f"v{current_string}"
            complete(old_tag, git_text("rev-parse", f"{old_tag}^{{commit}}"), runtime)
        fragments = pending()
        if not fragments:
            tag = f"v{current_string}" if current_string != "0.0.0" else ""
            if runtime and tag and not runtime.is_file():
                command("gh", "release", "download", tag, "--pattern", RUNTIME, "--output", str(runtime))
            outputs(tag=tag)
            return
        release_version, notes = next_release(current, fragments)
        tag = f"v{release_version}"
        update_metadata(release_version, notes, fragments)
        git("add", "-A", "--", str(PROPERTIES), str(CHANGELOG), str(FRAGMENTS))
        git("-c", "user.name=github-actions[bot]", "-c",
            "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit", "-m", f"chore(release): {tag}")
        commit = git_text("rev-parse", "HEAD")
        verify_metadata_commit(tip, commit)
        if push(branch, tag):
            complete(tag, commit, runtime)
            outputs(tag=tag)
            return
        print(f"Release race on attempt {attempt}/3. Refreshing the default branch before recomputing the version.")
    raise RuntimeError("Default branch kept moving after three release push attempts")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("preview", "preflight", "release", "image-preflight", "image-verify"))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--tag")
    args = parser.parse_args()
    try:
        if args.operation == "preview":
            fragments = pending()
            if fragments:
                value, notes = next_release(version(PROPERTIES.read_text(encoding="utf-8")), fragments)
                print(f"Next version {value}\n\n{notes}")
            else:
                print("No pending changesets")
        elif args.operation == "preflight":
            current = ".".join(map(str, version(PROPERTIES.read_text(encoding="utf-8"))))
            needed = bool(pending()) or needs_recovery(current)
            if needed and central_enabled():
                registries.preflight_central()
            if not needed:
                print("::notice::No pending changesets or missing core release artifacts.")
            outputs(needed=needed, current_tag=f"v{current}" if current != "0.0.0" else "")
        elif args.operation == "release":
            run_release(args.branch, args.runtime)
        elif args.operation == "image-preflight":
            repository = os.environ["GITHUB_REPOSITORY"]
            if not args.tag:
                raise ValueError("Expected a release tag")
            existing = registries.ghcr_platforms(repository, args.tag, authenticated=True)
            expected = {"linux/amd64", "linux/arm64"}
            if existing and existing != expected:
                raise RuntimeError(f"Refusing to overwrite the unexpected platform set for {args.tag}: {sorted(existing)}")
            if not existing:
                registries.preflight_ghcr(repository)
            else:
                print(f"::notice::GHCR already serves {args.tag}. Verify anonymously without publishing again.")
            outputs(needed=not existing)
        else:
            registries.wait_for(
                lambda: registries.ghcr_platforms(os.environ["GITHUB_REPOSITORY"], args.tag)
                == {"linux/amd64", "linux/arm64"},
                f"Anonymous multi-platform GHCR pull for {args.tag}", seconds=180,
            )
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
