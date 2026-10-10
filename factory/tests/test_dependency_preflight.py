"""Exercise the same dependency-tree gate used before CI starts wave zero."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.build_graph import plan
from tools.dependency_preflight import check, rpm_matches, write_factory_witnesses


class DependencyTreeTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        (self.root / "packages").mkdir()
        (self.root / "config").mkdir()
        self.rows = self.root / "rows"
        self.rows.mkdir()
        # Real namespaces and version floors; no fixed GNOME wave assignments.
        self.requirements = {"glib2": {"gcc"}, "gtk4": {"pkgconfig(glib-2.0) >= 2.90"},
                             "mutter": {"pkgconfig(gtk4) >= 4.24"},
                             "gnome-shell": {"pkgconfig(mutter-17) >= 51"}}
        self.provides = {"glib2": "pkgconfig(glib-2.0)", "gtk4": "pkgconfig(gtk4)",
                         "mutter": "pkgconfig(mutter-17)", "gnome-shell": "gnome-shell"}
        self.locks = []
        for name, requirements in self.requirements.items():
            package = self.root / "packages" / name
            package.mkdir()
            (package / f"{name}.spec").write_text(f"Name: {name}\n")
            self.locks.append({"name": name, "no_upstream_source": True})
            (self.rows / f"{name}.spec").write_text(f"Name: {name}\n")
            (self.rows / f"{name}.provides").write_text(self.provides[name] + "\n")
            (self.rows / f"{name}.br").write_text("\n".join(sorted(requirements)) + "\n")
        self.save_locks()
        (self.root / "config/gnome-stack.json").write_text(json.dumps({"targets": ["gnome-shell"]}))
        self.base = {name: {} for name in self.requirements}
        self.base["glib2"] = {"gcc": ["gcc-14.2.1-7.el10.x86_64"]}
        (self.rows / "base-satisfied.json").write_text(json.dumps(self.base))
        self.factory = {name: {requirement: {"matched": [provider for provider, cap in
                        self.provides.items() if requirement.split()[0] == cap], "unverified": []}
                        for requirement in requirements}
                        for name, requirements in self.requirements.items()}
        self.save_factory()

    def save_locks(self):
        (self.root / "config/upstream-sources.json").write_text(json.dumps({"schema": 1, "packages": self.locks}))

    def save_factory(self):
        (self.rows / "factory-satisfied.json").write_text(json.dumps(self.factory))

    def candidate(self):
        return plan(self.root, self.rows, stack=True)

    def test_target_closure_contains_prerequisites_and_checks_every_dependency(self):
        report = check(self.root, self.rows, self.candidate())
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["recipes"], 4)
        self.assertEqual(len(report["dependencies"]), 4)
        self.assertEqual(report["dependencies"][0]["base"], self.base["glib2"]["gcc"])

    def test_missing_external_provider_names_recipe_and_requirement(self):
        with (self.rows / "gtk4.br").open("a") as stream:
            stream.write("pkgconfig(missing-library) >= 1\n")
        self.factory["gtk4"]["pkgconfig(missing-library) >= 1"] = {"matched": [], "unverified": []}
        self.save_factory()
        report = check(self.root, self.rows, self.candidate())
        self.assertEqual(report["status"], "failed")
        self.assertIn("gtk4: pkgconfig(missing-library) >= 1", report["errors"][0])

    def test_too_old_factory_provider_cannot_pass_by_name(self):
        self.factory["gtk4"]["pkgconfig(glib-2.0) >= 2.90"]["matched"] = []
        self.save_factory()
        report = check(self.root, self.rows, self.candidate())
        self.assertEqual(report["status"], "failed")
        self.assertIn("glib-2.0", report["errors"][0])

    def test_generated_capability_requires_version_evidence(self):
        self.factory["gtk4"]["pkgconfig(glib-2.0) >= 2.90"] = {"matched": [], "unverified": ["glib2"]}
        self.save_factory()
        report = check(self.root, self.rows, self.candidate())
        self.assertIn("version unverified", report["errors"][0])

    def test_tampered_same_wave_or_omitted_prerequisite_is_rejected(self):
        candidate = self.candidate()
        candidate["waves"] = [["glib2", "gtk4", "mutter", "gnome-shell"]]
        with self.assertRaisesRegex(ValueError, "differs"):
            check(self.root, self.rows, candidate)
        candidate["waves"] = [["gtk4"], ["mutter"], ["gnome-shell"]]
        with self.assertRaisesRegex(ValueError, "differs"):
            check(self.root, self.rows, candidate)

    def test_selected_blocked_recipe_fails_before_building(self):
        self.locks[0]["blocked"] = True
        self.save_locks()
        with self.assertRaisesRegex(ValueError, "blocked recipes: glib2"):
            self.candidate()

    def test_cycle_without_base_witness_fails_before_building(self):
        (self.rows / "glib2.br").write_text("pkgconfig(gtk4) >= 4.24\n")
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.candidate()

    def test_unknown_target_is_actionable(self):
        (self.root / "config/gnome-stack.json").write_text('{"targets": ["typo"]}')
        with self.assertRaisesRegex(ValueError, "unknown GNOME targets: typo"):
            self.candidate()

    def test_unselected_blocked_recipe_does_not_block_the_stack(self):
        directory = self.root / "packages" / "unrelated"
        directory.mkdir()
        (directory / "unrelated.spec").write_text("Name: unrelated\n")
        self.locks.append({"name": "unrelated", "no_upstream_source": True, "blocked": True})
        self.save_locks()
        (self.rows / "unrelated.spec").write_text("Name: unrelated\n")
        (self.rows / "unrelated.br").write_text("")
        self.assertEqual(check(self.root, self.rows, self.candidate())["status"], "passed")

    def test_bootstrap_cycle_is_allowed_only_with_the_exact_base_version_witness(self):
        (self.rows / "glib2.br").write_text("pkgconfig(gtk4) >= 4.20\n")
        self.base["glib2"]["pkgconfig(gtk4) >= 4.20"] = ["gtk4-devel-4.20.0-1.el10.x86_64"]
        (self.rows / "base-satisfied.json").write_text(json.dumps(self.base))
        self.factory["glib2"]["pkgconfig(gtk4) >= 4.20"] = {"matched": ["gtk4"], "unverified": []}
        self.save_factory()
        self.assertEqual(check(self.root, self.rows, self.candidate())["status"], "passed")
        del self.base["glib2"]["pkgconfig(gtk4) >= 4.20"]
        (self.rows / "base-satisfied.json").write_text(json.dumps(self.base))
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.candidate()


@unittest.skipUnless(importlib.util.find_spec("rpm"), "version tests run in pinned CentOS extractor")
class CentOSRPMVersionTests(unittest.TestCase):
    def setUp(self):
        import rpm
        self.matches = lambda provide, requirement: rpm_matches(provide, requirement, rpm)

    def test_rpm_versions_include_epochs_prereleases_and_numeric_components(self):
        for provide, requirement, expected in [
                ("pkgconfig(gtk4) = 4.22", "pkgconfig(gtk4) >= 4.24", False),
                ("pkgconfig(gtk4) = 4.24.1", "pkgconfig(gtk4) >= 4.24", True),
                ("mutter = 51~rc", "mutter >= 51", False),
                ("tool = 1.0.10", "tool > 1.0.9", True),
                ("tool = 1:1.0", "tool >= 2.0", True),
                ("pkgconfig(gtk4)", "pkgconfig(gtk4) >= 4.24", False)]:
            with self.subTest(provide=provide, requirement=requirement):
                self.assertEqual(self.matches(provide, requirement), expected)

    def test_extraction_separates_incompatible_and_unverified_versions(self):
        with tempfile.TemporaryDirectory() as scratch:
            rows = Path(scratch)
            (rows / "consumer.br").write_text("pkgconfig(gtk4) >= 4.24\n")
            (rows / "gtk4.provides").write_text("pkgconfig(gtk4) = 4.22\n")
            (rows / "base-providers.json").write_text('{"gtk4": ["pkgconfig(gtk4)"]}')
            write_factory_witnesses(rows, self.matches)
            result = json.loads((rows / "factory-satisfied.json").read_text())
            self.assertEqual(result["consumer"]["pkgconfig(gtk4) >= 4.24"], {"matched": [], "unverified": []})
            (rows / "gtk4.provides").write_text("gtk4-devel = 4.24.1\n")
            write_factory_witnesses(rows, self.matches)
            result = json.loads((rows / "factory-satisfied.json").read_text())
            self.assertEqual(result["consumer"]["pkgconfig(gtk4) >= 4.24"]["unverified"], ["gtk4"])
