"""Regression coverage for source staging, graph reuse, and partial publication."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.assemble_repo import assemble, source_name
from tools.build_graph import plan
from tools.buildroot import resolve
from tools.inventory import inventory
from tools.source_pipeline import stage
from tools.rebuild_plan import select, input_digest
from tools.packit_workflow import package_names
from tools.publish_gate import did_build


class FactoryRepairs(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name) / 'factory'
        (self.root / 'packages').mkdir(parents=True)
        (self.root / 'config').mkdir()
        self.locks = []

    def recipe(self, name, **extra):
        directory = self.root / 'packages' / name
        directory.mkdir()
        (directory / f'{name}.spec').write_text(f'Name: {name}\n')
        self.locks.append(dict(name=name, no_upstream_source=True, **extra))
        (self.root / 'config/upstream-sources.json').write_text(json.dumps(
            dict(schema=1, packages=self.locks)))
        return directory

    def test_source_output_copies_every_verified_source(self):
        directory = self.recipe('demo')
        blob = b'archive'
        self.locks[0].pop('no_upstream_source')
        self.locks[0]['sources'] = [dict(url=f'https://example.org/{name}', filename=name,
                                      sha512=hashlib.sha512(blob).hexdigest())
                                   for name in ['one.tar.xz', 'two.tar.gz']]
        (self.root / 'config/upstream-sources.json').write_text(json.dumps(
            dict(schema=1, packages=self.locks)))
        output = self.root / 'out'
        with patch('tools.source_pipeline._fetch', return_value=blob):
            self.assertEqual(stage('demo', self.root, output), 0)
        for name in ['one.tar.xz', 'two.tar.gz']:
            self.assertEqual((output / name).read_bytes(), blob)

    def test_graph_reads_container_rows_without_running_host_rpm(self):
        self.recipe('provider')
        self.recipe('consumer')
        rows = self.root / 'rows'
        rows.mkdir()
        (rows / 'provider.spec').write_text('Name: provider\n')
        (rows / 'consumer.spec').write_text('BuildRequires: provider >= 1\n')
        with patch('tools.build_graph.subprocess.run', side_effect=AssertionError('host RPM')):
            self.assertEqual(plan(self.root, rows)['waves'], [['provider'], ['consumer']])
        (rows / 'consumer.spec').unlink()
        with self.assertRaises(FileNotFoundError):
            plan(self.root, rows)

    def test_manual_selection_forces_current_recipe_and_excludes_blocked_dependents(self):
        self.recipe('provider')
        self.recipe('blocked', blocked=True, blocked_reason='missing vendor archive')
        record = inventory(self.root)[1]
        witness = {'provider': input_digest(record, self.root)}
        result = select(self.root, witness, {'blocked': ['provider']}, only=['provider'])
        self.assertEqual(result['build_list'], ['provider'])
        self.assertEqual(package_names(self.root), ['provider'])
        with self.assertRaises(ValueError):
            select(self.root, {}, {}, only=['typo'])

    def test_partial_publish_keeps_failed_sources_and_removes_dropped_subpackages(self):
        seed = self.root / 'seed'; seed.mkdir()
        built = self.root / 'built'; built.mkdir()
        for name in ['gnome-shell-old.rpm', 'gnome-shell-dropped.rpm', 'gtk4-old.rpm']:
            (seed / name).write_bytes(b'old')
        (built / 'gnome-shell-new.rpm').write_bytes(b'new')
        def source(path):
            return 'gnome-shell' if path.name.startswith('gnome-shell') else 'gtk4'
        with patch('tools.assemble_repo.rpm_source', side_effect=source):
            self.assertEqual(assemble(seed, built, {'gnome-shell', 'gtk4'}), {'gnome-shell'})
        self.assertEqual(sorted(p.name for p in seed.iterdir()), ['gnome-shell-new.rpm', 'gtk4-old.rpm'])
        self.assertEqual(source_name('gnome-shell-50.0-1.el10.src.rpm'), 'gnome-shell')

    def test_buildroot_pulls_pin_and_refuses_mismatch(self):
        pin = 'quay.io/centos-bootc/centos-bootc:c10s@sha256:' + 'a' * 64
        from subprocess import CompletedProcess
        with patch('tools.buildroot.subprocess.run', side_effect=[
                CompletedProcess([], 0, '', ''), CompletedProcess([], 0, pin, '')]) as run:
            self.assertTrue(resolve(pin)['matches'])
            self.assertEqual(run.call_args_list[0].args[0], ['docker', 'pull', pin])
        with patch('tools.buildroot.subprocess.run', side_effect=[
                CompletedProcess([], 0, '', ''), CompletedProcess([], 0, 'wrong@sha256:' + 'b' * 64, '')]):
            with self.assertRaises(SystemExit):
                resolve(pin)

    def test_report_recognizes_real_multidigit_wave_names(self):
        self.assertTrue(did_build({'factory-rpm-s12-gnome-shell'}, 'gnome-shell'))
        self.assertFalse(did_build({'factory-rpm-s12-gnome-shell-devel'}, 'gnome-shell'))
