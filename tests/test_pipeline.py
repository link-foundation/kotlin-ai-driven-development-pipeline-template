"""Git-backed checks for the path and release metadata policies."""

import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ci
import registries
import release


class ChangeRoutingTest(unittest.TestCase):
    def test_docs_and_fragments_do_not_trigger_gradle(self):
        flags = ci.compare(PurePosixPath("."), ["docs/guide.md", ".changeset/note.md", ".gitkeep"], "")
        self.assertTrue(flags["docs"])
        self.assertFalse(flags["kotlin"])
        self.assertFalse(flags["production"])

    def test_monorepo_tracks_only_its_project_shared_inputs_and_workflows(self):
        project = PurePosixPath("kotlin")
        self.assertFalse(ci.compare(project, ["src/web.ts", "test/scripts-old/vectors.json"], "test/scripts")["kotlin"])
        self.assertTrue(ci.compare(project, ["test/scripts/vector with spaces.json"], "test/scripts")["kotlin"])
        self.assertTrue(ci.compare(project, ["kotlin/src/Old.kt"], "")["production"])
        self.assertTrue(ci.compare(project, [".github/workflows/kotlin.yml"], "")["workflow"])
        self.assertTrue(ci.compare(project, ["kotlin/Dockerfile"], "")["production"])

    def test_path_validation(self):
        for path in ("/tmp", "../outside", "project\ninjected=true"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                ci.project_path(path)


class GitPolicyTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        current = Path.cwd()
        os.chdir(self.scratch.name)
        self.addCleanup(os.chdir, current)
        ci.git("init", "-b", "main")
        ci.git("config", "user.name", "Fixture")
        ci.git("config", "user.email", "test@example.com")
        Path("gradle.properties").write_text("group=fixture\nversion=0.1.0\n")
        Path("CHANGELOG.md").write_text("# Changelog\n")
        Path(".changeset").mkdir()
        Path(".changeset/README.md").touch()
        Path("app.kt").write_text("base\n")
        self.commit("base")
        self.base = release.git_text("rev-parse", "HEAD")

    def commit(self, message):
        ci.git("add", "-A")
        ci.git("commit", "-m", message)

    def test_current_base_is_merged_and_compared_against_pull_request_only(self):
        ci.git("checkout", "-b", "feature")
        Path("new file.kt").touch()
        self.commit("feature")
        ci.git("checkout", "main")
        Path("base-only.kt").touch()
        self.commit("advance main")
        base = release.git_text("rev-parse", "HEAD")
        ci.git("checkout", "feature")
        ci.merge_base(base)
        self.assertTrue(Path("base-only.kt").exists())
        self.assertEqual(ci.diff_names(base), ["new file.kt"])

    def test_manual_version_and_missing_new_changeset_are_rejected(self):
        Path("app.kt").write_text("changed\n")
        self.commit("code")
        with self.assertRaisesRegex(ValueError, "require a new release note"):
            ci.check_metadata(PurePosixPath("."), self.base, True, True)
        Path(".changeset/note.md").write_text("---\nbump: patch\n---\n\nFix fixture.\n")
        self.commit("changeset")
        ci.check_metadata(PurePosixPath("."), self.base, True, True)
        Path("gradle.properties").write_text("group=fixture\nversion=0.1.1\n")
        self.commit("manual version")
        with self.assertRaisesRegex(ValueError, "Only the release workflow"):
            ci.check_metadata(PurePosixPath("."), self.base, True, True)

    def test_release_uses_highest_bump_and_commits_metadata_only(self):
        Path(".changeset/new-feature.md").write_text("---\nbump: minor\n---\n\nNew feature.\n")
        Path(".changeset/small-fix.md").write_text("---\nbump: patch\n---\n\nSmall fix.\n")
        self.commit("pending changesets")
        parent = release.git_text("rev-parse", "HEAD")
        fragments = release.pending()
        value, notes = release.next_release((0, 1, 0), fragments)
        self.assertEqual(value, "0.2.0")
        release.update_metadata(value, notes, fragments)
        self.commit("version")
        head = release.git_text("rev-parse", "HEAD")
        release.verify_metadata_commit(parent, head)
        self.assertEqual(release.pending(), [])
        self.assertIn("Small fix.", Path("CHANGELOG.md").read_text())
        Path("gradle.properties").write_text("group=changed\nversion=0.2.0\n")
        self.commit("unapproved metadata")
        with self.assertRaisesRegex(RuntimeError, "beyond release metadata"):
            release.verify_metadata_commit(head, release.git_text("rev-parse", "HEAD"))

    def test_lost_race_is_distinct_from_rule_refusal(self):
        response = subprocess.CompletedProcess([], 1, b"", b"! [rejected] (non-fast-forward)")
        with patch.object(release, "git", return_value=response):
            self.assertFalse(release.push("main", "v0.2.0"))
        response.stderr = b"remote: error: GH013: Repository rule violations found"
        with patch.object(release, "git", return_value=response), self.assertRaisesRegex(RuntimeError, "applicable"):
            release.push("main", "v0.2.0")


class RegistryTest(unittest.TestCase):
    def test_404_is_absent_and_rate_limit_is_unknown(self):
        with patch.object(registries, "request", side_effect=[(404, {}, b""), (429, {}, b"")]):
            self.assertFalse(registries.public_status("https://example.com/artifact"))
            with self.assertRaises(registries.UnknownRegistryState):
                registries.public_status("https://example.com/artifact")

    def test_already_published_central_deployment_is_never_republished(self):
        with patch.object(registries, "central_state", return_value="PUBLISHED"), patch.object(registries, "request") as api:
            self.assertTrue(registries.activate_deployment("fixture"))
            api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
