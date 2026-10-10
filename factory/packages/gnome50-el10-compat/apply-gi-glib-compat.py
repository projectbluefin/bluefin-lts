#!/usr/bin/env python3
"""
EL10 compatibility shim: GLib 2.87+ moved g_unix_signal_add to the GLibUnix-2.0
GI namespace. EL10's python3-gobject 3.46 gi/overrides/GLib.py only checks
hasattr(GLib, "unix_signal_add") which is False in newer GLib, so the
unix_signal_add_full compat alias is never set up either. This breaks
firewalld (AttributeError: 'gi.repository.GLib' object has no attribute
'unix_signal_add_full') and potentially other Python GI consumers.

This script patches gi/overrides/GLib.py to insert a fallback that imports
GLibUnix and maps GLib.unix_signal_add = GLibUnix.signal_add before the
existing hasattr check, restoring compatibility without removing the existing
deprecated_attr machinery.

It is idempotent: if the patch is already present, it does nothing.
It is invoked by gnome50-el10-compat %post and %filetriggerin so it
re-applies automatically if python3-gobject is reinstalled or updated.
"""

import glob
import os

MARKER = 'if hasattr(GLib, "unix_signal_add"):'
SENTINEL = "gnome50-el10-compat"

SHIM = """\
# {sentinel}: GLib 2.87+ moved g_unix_signal_add to GLibUnix-2.0 namespace.
# PyGObject 3.46 does not handle this mapping; shim it back for compatibility.
if not hasattr(GLib, "unix_signal_add"):
    try:
        import gi as _gi
        _gi.require_version("GLibUnix", "2.0")
        from gi.repository import GLibUnix as _GLibUnix
        if hasattr(_GLibUnix, "signal_add"):
            GLib.unix_signal_add = _GLibUnix.signal_add
    except Exception:
        pass
""".format(sentinel=SENTINEL)


def patch_file(path):
    try:
        with open(path) as f:
            content = f.read()
    except OSError:
        return

    if SENTINEL in content:
        return  # already patched

    if MARKER not in content:
        return  # unexpected file layout, skip

    patched = content.replace(MARKER, SHIM + MARKER, 1)
    with open(path, "w") as f:
        f.write(patched)


for glib_py in glob.glob(
    "/usr/lib/python3*/site-packages/gi/overrides/GLib.py"
):
    patch_file(glib_py)
