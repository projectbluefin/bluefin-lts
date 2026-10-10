"""Tests for the Packit SRPM gate's container invocation.

The bug this pins down is subtle and cost a CI run: ``docker -v host:container``
reads a *relative* host path as a volume name and rejects it with an error
about invalid characters for a local volume name. Nothing about the message
points at the fix, and the same mistake with a path that happens to be valid
syntax would have docker create an empty named volume and run the build
against nothing.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.inventory import factory_root, inventory
from tools.srpm_gate import command


def mounts(argv: list[str]) -> list[str]:
    """Return the host side of every -v mount.

    The value follows the flag, not the flag itself: indexing ``argv[index]``
    where ``argv[index] == "-v"`` yields the literal "-v" and every assertion
    below then passes for the wrong reason.
    """
    return [
        argv[index + 1].split(":", 1)[0]
        for index, item in enumerate(argv)
        if item == "-v"
    ]


class MountPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # factory_root takes the factory directory, not a path inside it.
        cls.root = factory_root(Path(__file__).resolve().parent.parent)
        cls.record = next(
            record for record in inventory(cls.root) if record.name == "gnome-shell"
        )

    def _command(self, output: Path):
        return command("gnome-shell", self.record, output, self.root, "packit:latest")

    def test_relative_output_still_yields_absolute_mounts(self):
        # The caller in the workflow passes --output work/srpm/<pkg>.src.rpm,
        # which is relative. This is the exact case that failed in CI.
        with tempfile.TemporaryDirectory() as scratch:
            cwd = Path.cwd()
            try:
                import os

                os.chdir(scratch)
                (Path(scratch) / "work" / "srpm").mkdir(parents=True)
                argv = self._command(Path("work/srpm/gnome-shell.src.rpm"))
            finally:
                import os

                os.chdir(cwd)

        for host in mounts(argv):
            self.assertTrue(
                Path(host).is_absolute(),
                f"mount source {host!r} is relative; docker reads it as a volume name",
            )

    def test_absolute_output_yields_absolute_mounts(self):
        with tempfile.TemporaryDirectory() as scratch:
            argv = self._command(Path(scratch) / "gnome-shell.src.rpm")
        for host in mounts(argv):
            self.assertTrue(Path(host).is_absolute())

    def test_missing_output_directory_is_refused(self):
        # Docker would create a missing host path as an empty named volume and
        # the build would run against nothing, silently.
        with tempfile.TemporaryDirectory() as scratch:
            missing = Path(scratch) / "does" / "not" / "exist" / "out.src.rpm"
            with self.assertRaises(ValueError) as caught:
                self._command(missing)
            self.assertIn("does not exist", str(caught.exception))

    def test_repository_mount_is_the_repository_not_the_factory(self):
        with tempfile.TemporaryDirectory() as scratch:
            argv = self._command(Path(scratch) / "out.src.rpm")
        repo_mounts = [host for host in mounts(argv) if host.endswith("bluefin-lts-1")]
        self.assertTrue(repo_mounts, "no mount for the repository root")

    def test_package_is_passed_through_the_environment(self):
        # packit_source0.py reads PACKAGE, so an entry that only passes -p
        # would produce a confusing failure inside the container.
        with tempfile.TemporaryDirectory() as scratch:
            argv = self._command(Path(scratch) / "out.src.rpm")
        self.assertIn("PACKAGE=gnome-shell", argv)

    def test_spec_path_is_repo_relative(self):
        # packit_source0.py resolves the spec against the repository root.
        with tempfile.TemporaryDirectory() as scratch:
            argv = self._command(Path(scratch) / "out.src.rpm")
        spec_env = next(item for item in argv if item.startswith("PACKIT_SPECFILE_PATH="))
        self.assertTrue(
            spec_env.split("=", 1)[1].startswith("factory/packages/gnome-shell/"),
            spec_env,
        )


if __name__ == "__main__":
    unittest.main()