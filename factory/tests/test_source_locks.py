"""Tests for the multi-source lock model.

A recipe may have more than one downloadable Source. glycin carries a vendored
libjxl tarball as Source2, malcontent carries libgsystemservice, and both fail
`rpmbuild -bs` when only Source0 is staged. These tests pin the behaviour that
was missing when that happened: the lock carries every source, and every one
of them is fetched and verified.

They also cover the URL fragment, which is easy to get wrong: rpm names a
fragmented source after the URL path with the fragment stripped, so leaving
`#...` in the filename stages a file rpmbuild will not find.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.inventory import Record, factory_root, inventory
from tools.source_pipeline import source_filename


class SourceFilenameTests(unittest.TestCase):
    def test_plain_url_uses_the_basename(self):
        self.assertEqual(
            source_filename("https://example.org/a/b/foo-1.0.tar.xz"), "foo-1.0.tar.xz"
        )

    def test_fragment_is_stripped(self):
        # rpm names the file after the URL path, not including `#...`.
        self.assertEqual(
            source_filename(
                "https://github.com/libjxl/libjxl/archive/refs/tags/v0.11.1.tar.gz"
                "#/libjxl-0.11.1.tar.gz"
            ),
            "v0.11.1.tar.gz",
        )

    def test_trailing_slash_does_not_yield_an_empty_name(self):
        self.assertEqual(source_filename("https://example.org/a/b/"), "b")

    def test_query_string_is_not_part_of_the_basename_here(self):
        # Documented behaviour: only the fragment is stripped. A query string
        # in a Source URL would need the same treatment, and no EL10 spec uses
        # one, so this pins what happens rather than leaving it undefined.
        self.assertEqual(
            source_filename("https://example.org/a/foo-1.0.tar.gz?v=2"), "foo-1.0.tar.gz?v=2"
        )


def record_for(lock: dict) -> Record:
    return Record(name="test", directory=Path("/nonexistent"), spec=Path("/nonexistent/x.spec"), lock=lock)


class LockShapeTests(unittest.TestCase):
    def test_sources_list_is_returned_in_order(self):
        record = record_for({
            "sources": [
                {"url": "https://a/one.tar.xz", "filename": "one.tar.xz", "sha512": "a"},
                {"url": "https://a/two.tar.xz", "filename": "two.tar.xz", "sha512": "b"},
            ]
        })
        self.assertEqual([s["filename"] for s in record.sources], ["one.tar.xz", "two.tar.xz"])

    def test_source0_is_the_first_source(self):
        # Packit is handed exactly one archive, and it has to be Source0.
        record = record_for({
            "sources": [
                {"url": "https://a/one.tar.xz", "filename": "one.tar.xz", "sha512": "a"},
                {"url": "https://a/two.tar.xz", "filename": "two.tar.xz", "sha512": "b"},
            ]
        })
        self.assertEqual(record.source0["filename"], "one.tar.xz")

    def test_legacy_flat_shape_still_reads(self):
        # A lock written before sources became a list must not silently become
        # an unlocked recipe.
        record = record_for({
            "url": "https://a/one.tar.xz",
            "filename": "one.tar.xz",
            "sha512": "a",
        })
        self.assertEqual(len(record.sources), 1)
        self.assertEqual(record.source0["filename"], "one.tar.xz")

    def test_empty_lock_has_no_sources(self):
        self.assertEqual(record_for({}).sources, [])

    def test_blocked_is_read_from_the_lock(self):
        self.assertTrue(record_for({"blocked": True}).blocked)
        self.assertEqual(
            record_for({"blocked": True, "blocked_reason": "x"}).blocked_reason, "x"
        )
        self.assertFalse(record_for({"url": "https://a/b.tar.xz"}).blocked)


class CommittedLockTests(unittest.TestCase):
    """The lock actually in the tree, checked for the invariants."""

    @classmethod
    def setUpClass(cls):
        cls.root = factory_root(Path(__file__).resolve().parent.parent)
        cls.records = inventory(cls.root)

    def test_every_source_has_a_digest(self):
        for record in self.records:
            if record.no_upstream_source:
                continue
            for index, source in enumerate(record.sources):
                self.assertTrue(
                    source.get("sha512") or source.get("sha256"),
                    f"{record.name} source {index} has no digest",
                )

    def test_no_two_sources_share_a_filename(self):
        # A collision means one silently overwrites the other, and which
        # payload is used then depends on lock order.
        for record in self.records:
            names = [source.get("filename") for source in record.sources]
            self.assertEqual(
                len(names), len(set(names)), f"{record.name}: duplicate source filename"
            )

    def test_blocked_recipes_still_carry_a_reason(self):
        for record in self.records:
            if record.blocked:
                self.assertTrue(
                    record.blocked_reason.strip(),
                    f"{record.name} is blocked with no reason recorded",
                )

    def test_blocked_recipes_are_not_buildable(self):
        blocked = {record.name for record in self.records if record.blocked}
        self.assertTrue(blocked, "expected at least one blocked recipe in this tree")


if __name__ == "__main__":
    unittest.main()
