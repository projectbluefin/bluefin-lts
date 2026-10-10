"""Tests for the publish gate and the failure report.

The gate is the last thing standing between a broken repository and a broken
image, so its decisions are pinned here -- particularly the decision *not* to
hold back a healthy build when an unrelated package fails.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.publish_gate import (
    artifact_for,
    did_build,
    failed_packages,
    marker,
    publish_allowed,
    render_report,
    with_marker,
)


class ArtifactTests(unittest.TestCase):
    def test_artifact_name_carries_the_stage_prefix(self):
        self.assertEqual(artifact_for("gtk4"), "factory-rpm-sgtk4")

    def test_did_build_reads_the_artifact_set(self):
        self.assertTrue(did_build({"factory-rpm-sgtk4"}, "gtk4"))
        self.assertFalse(did_build({"factory-rpm-smutter"}, "gtk4"))
        self.assertFalse(did_build(set(), "gtk4"))

    def test_prefix_is_not_matched_loosely(self):
        # gtk4 and gtk4-devel are different packages; a substring match would
        # credit one with the other's artifact.
        self.assertFalse(did_build({"factory-rpm-sgtk4-devel"}, "gtk4"))


class FailedPackagesTests(unittest.TestCase):
    def test_only_packages_without_an_artifact_fail(self):
        build_list = ["glib2", "gtk4", "mutter"]
        artifacts = {artifact_for("glib2"), artifact_for("mutter")}
        self.assertEqual(failed_packages(build_list, artifacts), ["gtk4"])

    def test_order_follows_the_build_list_not_the_set(self):
        build_list = ["mutter", "glib2"]
        artifacts = set()
        self.assertEqual(failed_packages(build_list, artifacts), ["mutter", "glib2"])

    def test_nothing_selected_is_nothing_failed(self):
        self.assertEqual(failed_packages([], set()), [])


class PublishDecisionTests(unittest.TestCase):
    def test_clean_run_publishes(self):
        allowed, _ = publish_allowed([], transaction_ok=True)
        self.assertTrue(allowed)

    def test_a_failure_does_not_hold_back_everything_else(self):
        # This is the decision the gate exists to make. Incremental
        # publication means one flaky package must not freeze the other 69.
        allowed, reason = publish_allowed(["fish"], transaction_ok=True)
        self.assertTrue(allowed)
        self.assertIn("previous build", reason)

    def test_a_failed_transaction_blocks_publication_outright(self):
        allowed, reason = publish_allowed([], transaction_ok=False)
        self.assertFalse(allowed)
        self.assertIn("transaction", reason)

    def test_a_failed_transaction_blocks_even_with_no_failures(self):
        # The dangerous case: everything built, and the result is still
        # unusable. Moving the tag here ships a broken image.
        allowed, _ = publish_allowed([], transaction_ok=False)
        self.assertFalse(allowed)


class ReportTests(unittest.TestCase):
    def test_report_names_the_failures(self):
        body = render_report(["glib2", "gtk4"], ["gtk4"], "https://example/run/1")
        self.assertIn("`gtk4`", body)
        self.assertIn("Did not build", body)
        self.assertIn("glib2", body)

    def test_report_states_the_incremental_consequence(self):
        body = render_report(["glib2", "gtk4"], ["gtk4"], "https://example/run/1")
        self.assertIn("keeps its previous build", body)

    def test_clean_report_says_so(self):
        body = render_report(["glib2"], [], "https://example/run/1")
        self.assertIn("Every selected package built", body)
        self.assertNotIn("Did not build", body)

    def test_empty_selection(self):
        body = render_report([], [], "https://example/run/1")
        self.assertIn("No packages were selected", body)

    def test_reasons_are_carried_through(self):
        body = render_report(["gtk4"], ["gtk4"], "u", {"gtk4": "tests failed"})
        self.assertIn("tests failed", body)

    def test_marker_round_trips(self):
        body = with_marker("report text", ["a", "b"])
        self.assertEqual(json.loads(marker(body)), ["a", "b"])

    def test_marker_absent_is_empty(self):
        self.assertEqual(marker("no marker here"), "")


class ReportCommandTests(unittest.TestCase):
    def test_end_to_end_through_the_cli(self):
        from tools.publish_gate import main

        build_list = ["glib2", "gtk4"]
        artifacts = {artifact_for("glib2")}
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            artifacts_path = root / "artifacts.json"
            artifacts_path.write_text(json.dumps(sorted(artifacts)))
            output = root / "report.md"
            failed = root / "failed.json"

            import contextlib
            import io
            import sys as _sys

            # The command reports each failure on stderr. Left to run, that
            # prints "did not build: gtk4" into the middle of the test output,
            # where it reads as a real failure and is easy to mistake for one
            # further down the log.
            captured = io.StringIO()
            argv = _sys.argv
            _sys.argv = [
                "publish_gate", "report",
                "--build-list", json.dumps(build_list),
                "--artifacts", str(artifacts_path),
                "--output", str(output),
                "--failed-output", str(failed),
                "--run-url", "https://example/run/2",
            ]
            try:
                with contextlib.redirect_stderr(captured):
                    self.assertEqual(main(), 0)
            finally:
                _sys.argv = argv

            self.assertIn("gtk4", captured.getvalue())
            self.assertEqual(json.loads(failed.read_text()), ["gtk4"])
            self.assertEqual(marker(output.read_text()), '["gtk4"]')


if __name__ == "__main__":
    unittest.main()
