"""Validate public references and build a local import draft, without network I/O."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile

from release import Invalid, need, parse_json, positive

PROFILE = Path(__file__).resolve().parents[1] / 'profiles' / 'create-client-local'
IDENTITY = {'name': 'Create Client Local Draft',
            'version': '0.0.0-local.20260913', 'author': 'Local assembly (provisional)'}
COLUMNS = ['filename', 'projectID', 'fileID', 'environment', 'license_label', 'file_page']


def validate_profile(manifest_bytes, catalogue_text):
    manifest = parse_json(manifest_bytes)
    need(isinstance(manifest, dict) and set(manifest) == {
        'minecraft', 'manifestType', 'manifestVersion', 'name', 'version',
        'author', 'files', 'overrides'}, 'unexpected manifest fields')
    need(manifest['manifestType'] == 'minecraftModpack' and
         type(manifest['manifestVersion']) is int and manifest['manifestVersion'] == 1 and
         manifest['overrides'] == 'overrides', 'unsupported draft format')
    need(all(manifest[k] == v for k, v in IDENTITY.items()), 'unexpected draft identity')
    need(manifest['minecraft'] == {'version': '1.21.1', 'modLoaders': [
        {'id': 'neoforge-21.1.250', 'primary': True}]} and
         manifest['minecraft']['modLoaders'][0]['primary'] is True,
         'unexpected Minecraft or loader')
    files = manifest['files']
    need(isinstance(files, list) and len(files) == 20, 'expected exactly 20 references')
    seen = set()
    for item in files:
        need(isinstance(item, dict) and set(item) == {'projectID', 'fileID', 'required'} and
             positive(item['projectID']) and positive(item['fileID']) and
             item['required'] is True, 'invalid required reference')
        need(item['projectID'] not in seen, 'duplicate project')
        seen.add(item['projectID'])
    reader = csv.DictReader(io.StringIO(catalogue_text), delimiter='\t')
    need(reader.fieldnames == COLUMNS, 'unexpected catalogue columns')
    rows = list(reader)
    need(len(rows) == 20, 'expected exactly 20 catalogue rows')
    names = set()
    for item, row in zip(files, rows):
        need(set(row) == set(COLUMNS) and all(isinstance(v, str) and v for v in row.values()),
             'invalid catalogue row')
        need(row['projectID'] == str(item['projectID']) and
             row['fileID'] == str(item['fileID']), 'catalogue/reference mismatch')
        need(re.fullmatch(r'[A-Za-z0-9_.+-]+\.jar', row['filename']) is not None,
             'unsafe catalogue filename')
        need(row['filename'].casefold() not in names, 'duplicate filename')
        names.add(row['filename'].casefold())
        need(row['environment'] in ('Client', 'Client & Server', 'Not Set'),
             'unexpected environment label')
        need(row['license_label'] in ('AGPLv3', 'All Rights Reserved', 'LGPLv3',
             'Custom License', 'MIT', 'LGPLv2.1', 'PolyForm Shield 1.0.0'),
             'unexpected license label')
        need(re.fullmatch(r'https://www\.curseforge\.com/minecraft/mc-mods/[a-z0-9-]+/files/' +
             re.escape(row['fileID']), row['file_page']) is not None,
             'only canonical public CurseForge file links are allowed')
    return manifest


def build(manifest):
    """Use only two fixed entries; never copy a profile directory or overrides."""
    content = (json.dumps(manifest, indent=2) + '\n').encode('utf-8')
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        for name, data, mode in [('manifest.json', content, 0o100644),
                                 ('overrides/', b'', 0o40755)]:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    blob = out.getvalue()
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        need(archive.namelist() == ['manifest.json', 'overrides/'] and
             archive.testzip() is None, 'invalid generated archive')
        need(archive.read('manifest.json') == content and
             archive.read('overrides/') == b'', 'archive content changed')
    return blob


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        # Validate all inputs before creating the output. No submission settings required.
        manifest = validate_profile((PROFILE / 'manifest.json').read_bytes(),
                                    (PROFILE / 'mods.tsv').read_text(encoding='utf-8'))
        need(args.output.suffix == '.zip', 'output must end with .zip')
        need(PROFILE.parents[1] / 'packs' not in args.output.resolve().parents,
             'local draft must not be placed in official exports directory packs/')
        blob = build(manifest)
        # Exclusive creation avoids replacing another artifact or following a symlink.
        with args.output.open('xb') as handle:
            handle.write(blob)
        print('Local reconstruction draft:', args.output)
        print('SHA256:', hashlib.sha256(blob).hexdigest())
        print('20 references; no jars/configs copied. App import and runtime not verified.')
        return 0
    except (Invalid, OSError, ValueError, KeyError, TypeError) as error:
        print('STOP:', error, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
