"""Synthetic fixtures only; never distribute these manifests as real exports."""
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import release as r


class ReleaseTests(unittest.TestCase):
    def fixture(self, extra=None, change=None):
        manifest = {'manifestType': 'minecraftModpack', 'manifestVersion': 1,
                    'name': 'Synthetic test', 'version': 'test', 'author': 'tests',
                    'overrides': 'overrides',
                    'minecraft': {'version': 'test-version', 'modLoaders': [
                        {'id': 'forge-test-loader', 'primary': True}]},
                    'files': [{'projectID': 1, 'fileID': 2, 'required': True}]}
        if change:
            change(manifest)
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('manifest.json', json.dumps(manifest))
            for name, content in (extra or {}).items():
                z.writestr(name, content)
        blob = out.getvalue()
        config = {'project_id': 1, 'minecraft_version': 'test-version',
                  'loader_id': 'forge-test-loader',
                  'game_version_names': ['test-version', 'Forge', 'Client'],
                  'release_type': 'alpha', 'display_name': 'Synthetic test',
                  'reviewed_sha256': hashlib.sha256(blob).hexdigest()}
        return blob, config

    def test_valid_synthetic_export(self):
        b, c = self.fixture({'overrides/config/example.toml': 'enabled = true'})
        self.assertEqual(r.validate(b, c), c['reviewed_sha256'])

    def test_paths_and_private_files(self):
        for name in ('../escape', '/absolute', 'overrides/../escape',
                     'overrides\\escape', 'C:/escape', 'wrapper/manifest.json',
                     'overrides/saves/test/level.dat', 'overrides/options.txt',
                     'overrides/servers.dat', 'overrides/.env', 'overrides/mods/mod.jar',
                     'overrides/logs/latest.log'):
            with self.subTest(name=name):
                b, c = self.fixture({name: 'test'})
                with self.assertRaises(r.Invalid):
                    r.validate(b, c)

    def test_sensitive_content_and_binary(self):
        for content in ('api_key = "not-a-real-key"', 'host=192.168.1.1',
                        'endpoint=https://example.invalid', 'host=server.internal', b'\xff'):
            with self.subTest(content=content):
                b, c = self.fixture({'overrides/config/test.txt': content})
                with self.assertRaises(r.Invalid):
                    r.validate(b, c)

    def test_metadata_mismatch(self):
        for key, value in (('minecraft_version', 'other'), ('loader_id', 'fabric-other'),
                           ('game_version_names', ['other']), ('project_id', None),
                           ('project_id', True), ('reviewed_sha256', '0' * 64)):
            with self.subTest(key=key):
                b, c = self.fixture()
                c[key] = value
                with self.assertRaises(r.Invalid):
                    r.validate(b, c)

    def test_manifest_bad_references(self):
        for change in (lambda m: m.update(files=[]),
                       lambda m: m['files'][0].update(fileID=True),
                       lambda m: m.update(manifestVersion=2),
                       lambda m: m['minecraft']['modLoaders'][0].update(primary=False)):
            b, c = self.fixture(change=change)
            with self.assertRaises(r.Invalid):
                r.validate(b, c)

    def test_limits_and_corruption(self):
        b, c = self.fixture()
        with patch.object(r, 'MAX_ZIP', 1), self.assertRaises(r.Invalid):
            r.validate(b, c)
        with patch.object(r, 'MAX_TOTAL', 1), self.assertRaises(r.Invalid):
            r.validate(b, c)
        with patch.object(r, 'MAX_ENTRIES', 0), self.assertRaises(r.Invalid):
            r.validate(b, c)
        b, c = self.fixture({'overrides/config/bomb.txt': 'a' * 100000})
        with self.assertRaises(r.Invalid):
            r.validate(b, c)
        c['reviewed_sha256'] = hashlib.sha256(b'broken').hexdigest()
        with self.assertRaises(zipfile.BadZipFile):
            r.validate(b'broken', c)

    def test_symlink_and_duplicate(self):
        for special in ('symlink', 'duplicate'):
            b, c = self.fixture()
            out = io.BytesIO(b)
            with zipfile.ZipFile(out, 'a') as z:
                entry = zipfile.ZipInfo('overrides/config/link')
                if special == 'symlink':
                    entry.create_system = 3
                    entry.external_attr = 0o120777 << 16
                else:
                    entry = 'MANIFEST.JSON'
                z.writestr(entry, 'target')
            b = out.getvalue()
            c['reviewed_sha256'] = hashlib.sha256(b).hexdigest()
            with self.assertRaises(r.Invalid):
                r.validate(b, c)

    def test_json_duplicate(self):
        with self.assertRaises(r.Invalid):
            r.parse_json('{"a":1,"a":2}')

    def test_changelog_required(self):
        _, c = self.fixture()
        for text in ('', 'REPLACE_ME'):
            with self.assertRaises(r.Invalid):
                r.metadata(c, text)

    def test_submit_same_bytes_and_header_only_token(self):
        b, c = self.fixture()
        r.validate(b, c)
        factory = Mock()
        conn = factory.return_value
        conn.getresponse.return_value.status = 200
        conn.getresponse.return_value.read.return_value = b'{"id":123}'
        self.assertEqual(r.submit(b, c, r.metadata(c, 'test changes'), 'dummy-token', factory), 123)
        method, path, body, headers = conn.request.call_args.args
        self.assertEqual(method, 'POST')
        self.assertEqual(path, '/api/projects/1/upload-file')
        self.assertIn(b, body)
        self.assertNotIn(b'dummy-token', body)
        self.assertEqual(headers['X-Api-Token'], 'dummy-token')
        conn.request.assert_called_once()
        conn.close.assert_called_once()

    def test_failure_and_redirect_never_retry(self):
        b, c = self.fixture()
        for status in (302, 401, 429, 500):
            factory = Mock()
            conn = factory.return_value
            conn.getresponse.return_value.status = status
            with self.assertRaises(r.Invalid):
                r.submit(b, c, {}, 'dummy-token', factory)
            conn.request.assert_called_once()

    def test_missing_token_no_network(self):
        b, c = self.fixture()
        factory = Mock()
        with self.assertRaises(r.Invalid):
            r.submit(b, c, {}, '', factory)
        factory.assert_not_called()

    def test_dry_run_no_network(self):
        import tempfile
        b, c = self.fixture()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'pack.zip').write_bytes(b)
            (root / 'release.json').write_text(json.dumps(c))
            (root / 'changes.md').write_text('test changes')
            args = ['release.py', '--zip', str(root / 'pack.zip'), '--config',
                    str(root / 'release.json'), '--changelog', str(root / 'changes.md')]
            with patch.object(sys, 'argv', args), patch.object(r, 'submit') as send:
                self.assertEqual(r.main(), 0)
                send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
