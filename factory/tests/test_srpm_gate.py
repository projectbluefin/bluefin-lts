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
        records = inventory(cls.root)
        if not records:
            raise unittest.SkipTest("no recipes to build a command from")
        # Any recipe will do. Naming a specific one couples the test to the
        # recipe inventory, so removing or renaming that package would fail
        # here for a reason that has nothing to do with the mount paths.
        cls.record = records[0]

    def _command(self, output: Path):
        return command(
            self.record.name, self.record, output, self.root, "packit:latest"
        )

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
        # Packit runs with /repo as its working directory, and
        # packit_source0.py resolves the spec against the repository root, so
        # this must be the repository. Mounting only factory/ would leave
        # .packit.yaml and build_scripts out of reach.
        #
        # Compared against the root computed from this file rather than a
        # literal directory name: the checkout is named differently in CI than
        # it is in a working copy, and hardcoding it makes the test fail for a
        # reason that has nothing to do with the code under test.
        with tempfile.TemporaryDirectory() as scratch:
            argv = self._command(Path(scratch) / "out.src.rpm")

        expected = str(self.root.parent.resolve())
        hosts = mounts(argv)
        self.assertIn(expected, hosts, f"repository root not mounted; got {hosts}")
        self.assertNotIn(str(self.root.resolve()), hosts)

    def test_package_is_passed_through_the_environment(self):
        # packit_source0.py reads PACKAGE, so an entry that only passes -p
        # would produce a confusing failure inside the container.
        with tempfile.TemporaryDirectory() as scratch:
            argv = self._command(Path(scratch) / "out.src.rpm")
        self.assertIn(f"PACKAGE={self.record.name}", argv)

    def test_spec_path_is_repo_relative(self):
        # packit_source0.py resolves the spec against the repository root, so
        # the path handed in must be repository-relative and name the recipe
        # directory -- never an absolute host path, which the container cannot
        # see.
        with tempfile.TemporaryDirectory() as scratch:
            argv = self._command(Path(scratch) / "out.src.rpm")
        spec_env = next(
            item for item in argv if item.startswith("PACKIT_SPECFILE_PATH=")
        )
        value = spec_env.split("=", 1)[1]
        self.assertFalse(Path(value).is_absolute(), value)
        self.assertTrue(value.startswith(f"factory/packages/{self.record.name}/"), value)


if __name__ == "__main__":
    unittest.main()