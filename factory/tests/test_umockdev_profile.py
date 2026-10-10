"""The umockdev syscall exception must preserve the upstream restrictions."""
import hashlib
import json
import unittest
from pathlib import Path


class UmockdevProfile(unittest.TestCase):
    def test_only_open_tree_is_added_to_pinned_default(self):
        root = Path(__file__).resolve().parents[1]
        profile = json.loads((root / 'config/seccomp/umockdev.json').read_text())
        extra = profile['syscalls'].pop()
        self.assertEqual(extra['names'], ['open_tree'])
        self.assertEqual(extra['action'], 'SCMP_ACT_ALLOW')
        self.assertEqual(extra['args'], [])
        self.assertEqual(profile['defaultAction'], 'SCMP_ACT_ERRNO')
        self.assertEqual(hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest(),
                         '2ebf3bdba229d3d972cfc3721001306de96cc5113a14b29cb510c2edd91ca84a')
