"""Keep recipe build exceptions scoped and preserve the pinned default policy."""
import hashlib
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.container_policy import apparmor_enabled, load, security_args


class ContainerPolicyTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def test_apparmor_changes_only_mount_and_pivot_permissions(self):
        profile = (self.root / 'packages/glycin/glycin.apparmor').read_text()
        additions = ('  # Mounts remain limited by the unchanged container capabilities and user namespace.\n'
                     '  mount,\n  pivot_root,')
        self.assertEqual(profile.count(additions), 1)
        baseline = profile.replace(additions, '  deny mount,')
        self.assertEqual(hashlib.sha256(baseline.encode()).hexdigest(),
                         'd8ea940b6b398e9d0868241bd0249cf5de82b5621d6d79778125e2089abf4b47')

    def test_policy_is_recipe_scoped_and_does_not_add_engine_privileges(self):
        with patch('tools.container_policy.apparmor_enabled', return_value=True):
            self.assertEqual(security_args(self.root, 'glycin'), [
                '--security-opt', f'seccomp={self.root}/packages/glycin/glycin-seccomp.json',
                '--security-opt', 'apparmor=bluefin-factory-glycin'])
            self.assertEqual(security_args(self.root, 'gtk4'), [])
            self.assertEqual(security_args(self.root, 'umockdev'), [
                '--security-opt', f'seccomp={self.root}/packages/umockdev/umockdev-seccomp.json'])

    def test_hosts_without_apparmor_retain_the_syscall_profile(self):
        with patch('tools.container_policy.apparmor_enabled', return_value=False), \
                patch('tools.container_policy.subprocess.run') as run:
            self.assertEqual(security_args(self.root, 'glycin'), [
                '--security-opt', f'seccomp={self.root}/packages/glycin/glycin-seccomp.json'])
            load(self.root)
            run.assert_not_called()

    def test_loader_loads_only_the_selected_recipe_profile(self):
        with patch('tools.container_policy.apparmor_enabled', return_value=True), \
                patch('tools.container_policy.subprocess.run') as run:
            load(self.root, 'glycin')
            run.assert_called_once_with([
                'sudo', '-n', 'apparmor_parser', '-r', '-T',
                str(self.root / 'packages/glycin/glycin.apparmor')], check=True)

    def test_no_policy_cli_emits_no_empty_docker_argument(self):
        output = subprocess.check_output([
            sys.executable, str(self.root / 'tools/container_policy.py'), 'args',
            '--root', str(self.root), '--package', 'gtk4'])
        self.assertEqual(output, b'')

    def test_apparmor_support_comes_from_the_engine_not_the_host_module(self):
        with patch('tools.container_policy.subprocess.check_output', return_value='{"apparmorEnabled": false}'):
            self.assertFalse(apparmor_enabled('podman'))
        with patch('tools.container_policy.subprocess.check_output', return_value='["name=seccomp"]'):
            self.assertFalse(apparmor_enabled('docker'))
        with patch('tools.container_policy.subprocess.check_output', return_value='["name=apparmor"]'):
            self.assertTrue(apparmor_enabled('docker'))
