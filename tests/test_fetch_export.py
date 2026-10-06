"""Network-free tests for same-repository, bounded, reviewed Release assets."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import fetch_export as f
import test_release as fixtures


class FetchExportTests(unittest.TestCase):
    def setUp(self):
        self.blob, self.config = fixtures.ReleaseTests().fixture()
        self.config['export_asset_id'] = 123

    def connection(self, status=200, body=b'', location=None):
        conn = Mock()
        conn.getresponse.return_value.status = status
        conn.getresponse.return_value.read.return_value = body
        conn.getresponse.return_value.getheader.return_value = location
        return conn

    def metadata(self, **changes):
        asset = {'id': 123, 'state': 'uploaded', 'size': len(self.blob)}
        asset.update(changes)
        return self.connection(body=json.dumps(asset).encode())

    def test_direct_download_has_fixed_repository_and_no_credentials(self):
        connections = [self.metadata(), self.connection(body=self.blob)]
        factory = Mock(side_effect=connections)
        self.assertEqual(f.fetch(self.config, factory), self.blob)
        self.assertEqual(factory.call_count, 2)
        for conn in connections:
            method, path = conn.request.call_args.args
            self.assertEqual(method, 'GET')
            self.assertEqual(path, '/repos/aiagate/minecraft-modpack-release/releases/assets/123')
            self.assertNotIn('Authorization', conn.request.call_args.kwargs['headers'])
            self.assertNotIn('X-Api-Token', conn.request.call_args.kwargs['headers'])
            conn.request.assert_called_once()
            conn.close.assert_called_once()

    def test_single_github_https_redirect_is_allowed_without_credentials(self):
        cdn = self.connection(body=self.blob)
        factory = Mock(side_effect=[self.metadata(), self.connection(
            302, location='https://release-assets.githubusercontent.com/path?signature=dummy'), cdn])
        self.assertEqual(f.fetch(self.config, factory), self.blob)
        self.assertEqual(factory.call_args.args[0], 'release-assets.githubusercontent.com')
        self.assertEqual(cdn.request.call_args.args, ('GET', '/path?signature=dummy'))
        self.assertNotIn('Authorization', cdn.request.call_args.kwargs['headers'])

    def test_arbitrary_private_and_credential_redirects_rejected(self):
        for url in ('http://objects.githubusercontent.com/path',
                    'https://127.0.0.1/path', 'https://example.invalid/path',
                    'https://objects.githubusercontent.com.example.invalid/path',
                    'https://dummy-secret@objects.githubusercontent.com/path',
                    'https://objects.githubusercontent.com:444/path',
                    'https://objects.githubusercontent.com/path#fragment',
                    'https://objects.githubusercontent.com/path\r\nInjected: value'):
            factory = Mock(side_effect=[self.metadata(), self.connection(302, location=url)])
            with self.subTest(url=url), self.assertRaises(f.Invalid) as error:
                f.fetch(self.config, factory)
            self.assertEqual(factory.call_count, 2)
            self.assertNotIn('dummy-secret', str(error.exception))

    def test_invalid_asset_id_fails_before_network(self):
        for asset_id in (None, True, 0, -1, '123/../../other', '$(touch /tmp/unwanted)'):
            config = dict(self.config, export_asset_id=asset_id)
            factory = Mock()
            with self.subTest(asset_id=asset_id), self.assertRaises(f.Invalid):
                f.fetch(config, factory)
            factory.assert_not_called()

    def test_metadata_limits_mismatch_and_changed_bytes_rejected(self):
        for changes in ({'id': 124}, {'id': True}, {'size': f.MAX_ZIP + 1},
                        {'size': 0}, {'state': 'starter'}):
            factory = Mock(return_value=self.metadata(**changes))
            with self.subTest(changes=changes), self.assertRaises(f.Invalid):
                f.fetch(self.config, factory)
            factory.assert_called_once()
        for blob in (b'changed', b'X' * len(self.blob)):
            factory = Mock(side_effect=[self.metadata(), self.connection(body=blob)])
            with self.assertRaises(f.Invalid):
                f.fetch(self.config, factory)

    def test_timeout_errors_and_second_redirect_never_retry(self):
        for status in (401, 404, 429, 500):
            conn = self.connection(status)
            factory = Mock(return_value=conn)
            with self.assertRaises(f.Invalid):
                f.fetch(self.config, factory)
            conn.request.assert_called_once()
            conn.close.assert_called_once()
        conn = self.metadata()
        conn.getresponse.side_effect = TimeoutError('dummy signed URL or secret')
        with self.assertRaises(f.Invalid) as error:
            f.fetch(self.config, Mock(return_value=conn))
        self.assertNotIn('dummy signed URL or secret', str(error.exception))
        factory = Mock(side_effect=[self.metadata(), self.connection(
            302, location='https://objects.githubusercontent.com/path'),
            self.connection(302, location='https://objects.githubusercontent.com/again')])
        with self.assertRaises(f.Invalid):
            f.fetch(self.config, factory)
        self.assertEqual(factory.call_count, 3)

    def test_body_reads_are_bounded(self):
        conn = self.connection(body=b'x' * 101)
        with self.assertRaises(f.Invalid):
            f.get(f.API_HOST, '/test', 'application/json', 100, Mock(return_value=conn))
        conn.getresponse.return_value.read.assert_called_once_with(101)
        conn.close.assert_called_once()

    def test_cli_never_saves_unvalidated_or_overwrites_existing_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            config = root / 'release.json'
            config.write_text(json.dumps(self.config))
            out = root / 'pack.zip'
            args = ['fetch_export.py', '--config', str(config), '--output', str(out)]
            with patch.object(sys, 'argv', args), patch.object(f, 'fetch', side_effect=f.Invalid('dummy failure')):
                self.assertEqual(f.main(), 1)
            self.assertFalse(out.exists())
            out.write_bytes(b'existing')
            with patch.object(sys, 'argv', args), patch.object(f, 'fetch') as fetch:
                self.assertEqual(f.main(), 1)
                fetch.assert_not_called()
            self.assertEqual(out.read_bytes(), b'existing')


if __name__ == '__main__':
    unittest.main()
