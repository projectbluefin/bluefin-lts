"""Tests for the rpm version comparator and source selection.

``rpmvercmp`` is the piece of this factory most likely to be subtly wrong,
because Python's own ordering disagrees with rpm's in cases that occur in real
package names. These tests pin the disagreements rather than the agreements.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.import_srpm import select_source
from tools.import_srpm import rpmvercmp


def entries(*pairs: tuple[str, str, str]) -> dict[str, dict]:
    """Build a metadata index from (href, version, release) triples."""
    return {
        href: {"name": name, "version": version, "release": release, "checksum": "x",
               "checksum_type": "sha256"}
        for href, name, version, release in (
            (href, name, version, release) for href, name, version, release in pairs
        )
    }


class RpmVerCmpTests(unittest.TestCase):
    def test_equal(self):
        self.assertEqual(rpmvercmp("50.0", "50.0"), 0)

    def test_numeric_order_is_not_string_order(self):
        # The whole reason this function exists. Python sorts "9" after "10";
        # rpm does not.
        self.assertEqual(rpmvercmp("1.0.0.10", "1.0.0.9"), 1)
        self.assertEqual(rpmvercmp("1.0.0.9", "1.0.0.10"), -1)

    def test_tilde_sorts_before_release(self):
        # 50.0 must beat 50~rc. A string sort picks the release candidate,
        # which would seed the whole desktop from RCs.
        self.assertEqual(rpmvercmp("50.0", "50~rc"), 1)
        self.assertEqual(rpmvercmp("50~rc", "50.0"), -1)

    def test_tilde_sorts_before_end_of_string(self):
        self.assertEqual(rpmvercmp("1.0", "1.0~rc"), 1)
        self.assertEqual(rpmvercmp("1.0~rc", "1.0"), -1)

    def test_caret_sorts_after_end_of_string_but_before_content(self):
        # `^` sorts *after* the end of the string but before any real content.
        # So 1.0^post is newer than 1.0, and older than 1.0.1. Reading it the
        # other way round would import a post-release over its own successor.
        self.assertEqual(rpmvercmp("1.0", "1.0^post"), -1)
        self.assertEqual(rpmvercmp("1.0^post", "1.0"), 1)
        self.assertEqual(rpmvercmp("1.0^post", "1.0.1"), -1)

    def test_leading_zeroes_do_not_change_ordering(self):
        self.assertEqual(rpmvercmp("1.007", "1.7"), 0)
        self.assertEqual(rpmvercmp("1.010", "1.10"), 0)

    def test_numeric_segment_beats_alphabetic(self):
        self.assertEqual(rpmvercmp("1.1", "1.a"), 1)
        self.assertEqual(rpmvercmp("1.a", "1.1"), -1)

    def test_longer_is_greater_when_prefix_equal(self):
        self.assertEqual(rpmvercmp("1.0.1", "1.0"), 1)
        self.assertEqual(rpmvercmp("1.0", "1.0.1"), -1)

    def test_empty_is_lowest(self):
        self.assertEqual(rpmvercmp("", "1.0"), -1)
        self.assertEqual(rpmvercmp("1.0", ""), 1)

    def test_gnome_versions_seeded_in_practice(self):
        # The versions this chroot actually carries, in the order the seeder
        # must choose them.
        self.assertEqual(rpmvercmp("50.0", "50~rc"), 1)
        self.assertEqual(rpmvercmp("4.22.1", "4.21.6"), 1)
        self.assertEqual(rpmvercmp("2.88.0", "2.87.3"), 1)
        self.assertEqual(rpmvercmp("1.9.0", "1.9~rc"), 1)


class SelectSourceTests(unittest.TestCase):
    def test_single_archive(self):
        index = entries(("a.src.rpm", "gnome-shell", "50.0", "1"))
        self.assertEqual(select_source(index, "gnome-shell", None), "a.src.rpm")

    def test_newest_release_of_one_version_wins(self):
        # Rebuilds of the same source are not a decision: take the newest.
        index = entries(
            ("a.src.rpm", "glib2", "2.88.0", "1"),
            ("b.src.rpm", "glib2", "2.88.0", "4"),
            ("c.src.rpm", "glib2", "2.88.0", "3"),
        )
        self.assertEqual(select_source(index, "glib2", "2.88.0"), "b.src.rpm")

    def test_several_versions_is_refused(self):
        index = entries(
            ("a.src.rpm", "gnome-shell", "50.0", "3"),
            ("b.src.rpm", "gnome-shell", "50~rc", "2"),
        )
        with self.assertRaises(ValueError) as caught:
            select_source(index, "gnome-shell", None)
        self.assertIn("several versions", str(caught.exception))

    def test_release_candidate_loses_to_release_when_asked_for_rc(self):
        index = entries(
            ("a.src.rpm", "gnome-shell", "50.0", "3"),
            ("b.src.rpm", "gnome-shell", "50~rc", "2"),
        )
        self.assertEqual(select_source(index, "gnome-shell", "50~rc"), "b.src.rpm")

    def test_absent_package(self):
        with self.assertRaises(ValueError):
            select_source(entries(("a.src.rpm", "glib2", "2.88.0", "1")), "gnome-shell", None)

    def test_absent_version_names_what_is_available(self):
        index = entries(("a.src.rpm", "glib2", "2.88.0", "1"))
        with self.assertRaises(ValueError) as caught:
            select_source(index, "glib2", "9.9.9")
        self.assertIn("2.88.0", str(caught.exception))

    def test_selection_is_deterministic_regardless_of_dict_order(self):
        pair = entries(
            ("a.src.rpm", "p", "1.0", "1"),
            ("b.src.rpm", "p", "1.0", "2"),
        )
        forward = select_source(pair, "p", "1.0")
        reversed_index = dict(reversed(list(pair.items())))
        self.assertEqual(select_source(reversed_index, "p", "1.0"), forward)


if __name__ == "__main__":
    unittest.main()
