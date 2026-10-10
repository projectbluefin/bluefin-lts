"""Recipe syscall exceptions must preserve the upstream restrictions."""
import hashlib
import json
import unittest
from pathlib import Path


class RecipeProfiles(unittest.TestCase):
    def test_only_required_syscalls_are_added_to_pinned_default(self):
        root = Path(__file__).resolve().parents[1]
        allowed = {
            'umockdev': ['open_tree'],
            'glycin': ['clone', 'unshare', 'mount', 'umount2', 'pivot_root', 'sethostname'],
        }
        for package, names in allowed.items():
            with self.subTest(package=package):
                path = root / 'packages' / package / f'{package}-seccomp.json'
                profile = json.loads(path.read_text())
                extra = profile['syscalls'].pop()
                self.assertEqual(extra['names'], names)
                self.assertEqual(extra['action'], 'SCMP_ACT_ALLOW')
                self.assertEqual(extra['args'], [])
                self.assertEqual(profile['defaultAction'], 'SCMP_ACT_ERRNO')
                self.assertEqual(hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest(),
                                 '2ebf3bdba229d3d972cfc3721001306de96cc5113a14b29cb510c2edd91ca84a')
