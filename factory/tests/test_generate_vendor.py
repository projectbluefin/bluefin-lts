"""Check offline cargo bundles, registry checksums, and archive safety."""
import hashlib
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.generate_vendor import cargo_lock_packages, generate, _vendored_crate_members


def archive(name, data):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as tar:
        member = tarfile.TarInfo(name)
        member.size = len(data)
        tar.addfile(member, io.BytesIO(data))
    return output.getvalue()


class VendorTests(unittest.TestCase):
    def test_bundle_reproducible_and_uses_verified_cache(self):
        crate = archive('demo-1.0.0/Cargo.toml', b'[package]\nname="demo"\nversion="1.0.0"\n')
        checksum = hashlib.sha256(crate).hexdigest()
        lock = ('[[package]]\nname="demo"\nversion="1.0.0"\n'
                'source="registry+https://github.com/rust-lang/crates.io-index"\n'
                f'checksum="{checksum}"\n').encode()
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            source = root / 'upstream.tar.gz'
            source.write_bytes(archive('upstream/Cargo.lock', lock))
            with patch('tools.source_pipeline._fetch', return_value=crate) as fetch:
                first = generate(source, root / 'first.tar.xz')
                second = generate(source, root / 'second.tar.xz')
            self.assertEqual(first.read_bytes(), second.read_bytes())
            fetch.assert_called_once()
            with tarfile.open(first) as tar:
                self.assertIsNotNone(tar.extractfile('vendor/demo-1.0.0/.cargo-checksum.json'))

    def test_git_dependencies_cannot_enter_an_offline_bundle(self):
        with self.assertRaisesRegex(RuntimeError, 'not crates.io'):
            cargo_lock_packages('[[package]]\nname="demo"\nversion="1.0.0"\nsource="git+https://example.com/demo"\n')

    def test_crate_checksum_and_traversal_are_rejected(self):
        payload = archive('demo-1.0.0/../../escape', b'bad')
        crate = {'name': 'demo', 'version': '1.0.0', 'checksum': '0' * 64}
        with self.assertRaisesRegex(RuntimeError, 'expected sha256'):
            list(_vendored_crate_members(crate, payload, 'vendor', 0))
        crate['checksum'] = hashlib.sha256(payload).hexdigest()
        with self.assertRaisesRegex(RuntimeError, 'unsafe path'):
            list(_vendored_crate_members(crate, payload, 'vendor', 0))
