"""Verify the public reconstruction and reject unsafe or drifting references."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import local_pack as p


class LocalPackTests(unittest.TestCase):
    def setUp(self):
        self.raw = (p.PROFILE / 'manifest.json').read_bytes()
        self.manifest = json.loads(self.raw)
        self.catalogue = (p.PROFILE / 'mods.tsv').read_text(encoding='utf-8')

    def test_current_profile_and_reproducible_two_entry_archive(self):
        manifest = p.validate_profile(self.raw, self.catalogue)
        first = p.build(manifest)
        self.assertEqual(first, p.build(manifest))
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            self.assertEqual(archive.namelist(), ['manifest.json', 'overrides/'])
            self.assertIsNone(archive.testzip())
            self.assertEqual(json.loads(archive.read('manifest.json')), self.manifest)
            self.assertEqual(archive.read('overrides/'), b'')

    def test_reject_duplicate_optional_boolean_and_extra_fields(self):
        changes = [lambda m: m['files'][1].update(projectID=m['files'][0]['projectID']),
                   lambda m: m['files'][0].update(required=False),
                   lambda m: m['files'][0].update(fileID=True),
                   lambda m: m.update(extra='unexpected'),
                   lambda m: m['files'].pop()]
        for change in changes:
            m = copy.deepcopy(self.manifest)
            change(m)
            with self.subTest(change=change), self.assertRaises(p.Invalid):
                p.validate_profile(json.dumps(m), self.catalogue)

    def test_reject_catalogue_drift_and_nonofficial_links(self):
        for catalogue in [self.catalogue.replace('8777573', '8777574', 1),
                          self.catalogue.replace('https://www.curseforge.com/', 'https://example.invalid/'),
                          self.catalogue.replace('create_connected-1.3.3-mc1.21.1.jar', '../mod.jar')]:
            with self.subTest(catalogue=catalogue[:30]), self.assertRaises(p.Invalid):
                p.validate_profile(self.raw, catalogue)

    def test_reject_changed_loader_or_identity(self):
        for change in [lambda m: m['minecraft']['modLoaders'][0].update(id='forge-52.1.16'),
                       lambda m: m['minecraft']['modLoaders'][0].update(primary=1),
                       lambda m: m.update(author='unexpected')]:
            m = copy.deepcopy(self.manifest)
            change(m)
            with self.assertRaises(p.Invalid):
                p.validate_profile(json.dumps(m), self.catalogue)

    def test_cli_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'draft.zip'
            out.write_bytes(b'existing')
            with patch.object(sys, 'argv', ['local_pack.py', '--output', str(out)]):
                self.assertEqual(p.main(), 1)
            self.assertEqual(out.read_bytes(), b'existing')

    def test_cli_rejects_official_export_directory(self):
        out = p.PROFILE.parents[1] / 'packs' / 'local-draft.zip'
        with patch.object(sys, 'argv', ['local_pack.py', '--output', str(out)]):
            self.assertEqual(p.main(), 1)
        self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
