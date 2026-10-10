"""Tests for the BuildRequires graph and wave solver.

The solver is what replaces hand-assigned build stages, so the properties that
matter are: a package never lands in a wave before something it needs, a cycle
is named rather than silently dropping members, and the output is stable.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.build_graph import (
    parse_rows,
    resolve_edges,
    reverse_dependencies,
    waves,
)


class ParseRowsTests(unittest.TestCase):
    def test_round_trip(self):
        text = "gtk4\tglib2 >= 2.86\nmutter\tgtk4\n"
        rows = parse_rows(text)
        self.assertEqual(rows["gtk4"], {"glib2 >= 2.86"})
        self.assertEqual(rows["mutter"], {"gtk4"})

    def test_blank_lines_ignored(self):
        self.assertEqual(parse_rows("\n\na\tb\n\n"), {"a": {"b"}})

    def test_malformed_row_is_rejected(self):
        # Silently skipping a row would remove a BuildRequires edge, which
        # orders a package before the thing it needs.
        with self.assertRaises(ValueError):
            parse_rows("gtk4\n")


class ResolveEdgesTests(unittest.TestCase):
    def test_only_factory_packages_become_edges(self):
        rows = {"gtk4": {"gcc", "glib2", "meson"}, "mutter": {"gtk4"}}
        edges = resolve_edges(rows, {"gtk4", "mutter", "glib2"})
        # gcc and meson are in the build root already, so they place no
        # constraint on our ordering. glib2 is not, so it does.
        self.assertEqual(edges["gtk4"], {"glib2"})
        self.assertEqual(edges["mutter"], {"gtk4"})

    def test_package_never_depends_on_itself(self):
        edges = resolve_edges({"gtk4": {"gtk4"}}, {"gtk4"})
        self.assertEqual(edges.get("gtk4", set()), set())

    def test_unknown_package_is_dropped(self):
        rows = {"nonexistent": {"gtk4"}}
        self.assertEqual(resolve_edges(rows, {"gtk4"}), {})

    def test_alternation_keeps_every_candidate(self):
        # Over-approximating only makes a wave later than necessary;
        # under-approximating breaks the build.
        edges = resolve_edges({"nautilus": {"(glycin or libgda)"}}, {"nautilus", "glycin", "libgda"})
        self.assertEqual(edges["nautilus"], {"glycin", "libgda"})

    def test_boolean_operators_are_not_treated_as_packages(self):
        edges = resolve_edges(
            {"nautilus": {"(glycin with gtk4 and libgda)"}},
            {"nautilus", "glycin", "gtk4", "libgda"},
        )
        self.assertNotIn("with", edges["nautilus"])
        self.assertNotIn("and", edges["nautilus"])
        self.assertIn("glycin", edges["nautilus"])


class WaveTests(unittest.TestCase):
    def test_linear_chain_gets_one_package_per_wave(self):
        edges = {"c": {"b"}, "b": {"a"}}
        self.assertEqual(waves(edges, ["a", "b", "c"]), [["a"], ["b"], ["c"]])

    def test_independent_packages_share_a_wave(self):
        edges = {"c": {"a"}, "b": {"a"}}
        self.assertEqual(waves(edges, ["a", "b", "c"]), [["a"], ["b", "c"]])

    def test_no_edges_means_one_wave(self):
        self.assertEqual(waves({}, ["a", "b", "c"]), [["a", "b", "c"]])

    def test_cycle_is_named(self):
        # Dropping the members silently is how a recipe stops being built.
        with self.assertRaises(ValueError) as caught:
            waves({"a": {"b"}, "b": {"a"}}, ["a", "b"])
        self.assertIn("cycle", str(caught.exception))
        self.assertIn("a", str(caught.exception))
        self.assertIn("b", str(caught.exception))

    def test_self_dependency_is_ignored_not_a_cycle(self):
        # A package BuildRequires-ing itself is a way of saying "rebuild me",
        # not an ordering constraint. resolve_edges already drops it; waves
        # ignores it too so a hand-written plan row cannot wedge the solver.
        self.assertEqual(waves({"a": {"a"}}, ["a"]), [["a"]])

    def test_output_is_stable_across_input_ordering(self):
        edges = {"c": {"a"}, "b": {"a"}, "d": {"b"}}
        first = waves(edges, ["a", "b", "c", "d"])
        second = waves(edges, ["d", "c", "b", "a"])
        self.assertEqual(first, second)

    def test_every_package_appears_exactly_once(self):
        edges = {"c": {"a", "b"}, "b": {"a"}, "e": {"d", "c"}}
        packages = ["a", "b", "c", "d", "e"]
        flattened = [p for wave in waves(edges, packages) for p in wave]
        self.assertEqual(sorted(flattened), sorted(packages))
        self.assertEqual(len(flattened), len(set(flattened)))

    def test_dependency_always_precedes_dependent(self):
        edges = {
            "d": {"c", "b"},
            "c": {"b"},
            "e": {"a", "d"},
        }
        packages = ["a", "b", "c", "d", "e"]
        position = {}
        for index, wave in enumerate(waves(edges, packages)):
            for package in wave:
                position[package] = index
        for package, predecessors in edges.items():
            for predecessor in predecessors:
                self.assertLess(
                    position[predecessor],
                    position[package],
                    f"{predecessor} must build before {package}",
                )


class ReverseDependencyTests(unittest.TestCase):
    def test_inverts_the_graph(self):
        edges = {"mutter": {"gtk4"}, "gnome-shell": {"mutter", "gtk4"}}
        reverse = reverse_dependencies(edges, ["gtk4", "mutter", "gnome-shell"])
        self.assertEqual(reverse["gtk4"], {"mutter", "gnome-shell"})
        self.assertEqual(reverse["mutter"], {"gnome-shell"})
        self.assertEqual(reverse["gnome-shell"], set())

    def test_unknown_package_has_no_dependents(self):
        reverse = reverse_dependencies({}, ["gtk4"])
        self.assertEqual(reverse["gtk4"], set())


if __name__ == "__main__":
    unittest.main()
