"""Validate an untouched CurseForge App export; optionally submit the same bytes."""
import argparse
import hashlib
import html
import http.client
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid
import zipfile

MAX_ZIP = 90 * 1024 * 1024  # Repository policy, not a CurseForge API limit.
MAX_TOTAL = 256 * 1024 * 1024
MAX_ENTRY = 32 * 1024 * 1024
MAX_ENTRIES = 10000
HOST = 'minecraft.curseforge.com'
DENIED = {'saves', 'world', 'worlds', 'logs', 'crash-reports', 'screenshots',
          'backups', 'options.txt', 'optionsof.txt', 'servers.dat', 'servers.dat_old',
          'server.properties', 'whitelist.json', 'ops.json', 'usercache.json',
          'secrets', 'credentials', 'session.lock', 'level.dat', 'playerdata'}
SENSITIVE = re.compile(rb'(?i)(-----BEGIN [A-Z ]*PRIVATE KEY|'
                       rb'(?:password|passwd|token|api[_-]?key|secret)\s*["\x27]?\s*[:=]\s*["\x27]?[^\s"\x27,}]{4,}|'
                       rb'https?://|(?:\d{1,3}\.){3}\d{1,3}|'
                       rb'(?:localhost|[a-z0-9.-]+\.(?:local|lan|internal))\b)')
PUBLIC_MODLIST_URL = re.compile(
    rb'https?://(?:(?:www|minecraft)\.)?curseforge\.com/'
    rb'(?:minecraft/mc-mods/[a-z0-9-]+(?:/files/[0-9]+)?|projects/[a-z0-9-]+)/?'
    rb'(?=[\s"\x27<>]|$)', re.IGNORECASE)


class Invalid(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise Invalid(message)


def positive(value):
    return type(value) is int and value > 0


def parse_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'JSON has duplicate keys')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique)


def config_check(config):
    need(isinstance(config, dict), 'config must be an object')
    need(set(config) == {'project_id', 'minecraft_version', 'loader_id',
                        'game_version_names', 'release_type', 'display_name',
                        'reviewed_sha256', 'export_asset_id'}, 'config keys do not match release.example.json')
    need(config['export_asset_id'] is None or positive(config['export_asset_id']),
         'export_asset_id must be null for local checks or a positive integer')
    need(positive(config['project_id']), 'project_id is not configured')
    for key in ('minecraft_version', 'loader_id', 'display_name'):
        need(isinstance(config[key], str) and config[key].strip() and
             'REPLACE' not in config[key] and len(config[key]) < 200,
             key + ' is not configured')
    need(config['release_type'] in ('alpha', 'beta', 'release'), 'invalid release_type')
    names = config['game_version_names']
    need(isinstance(names, list) and len(names) == 3 and
         all(isinstance(n, str) for n in names), 'set exactly Minecraft, loader, Client game version names')
    family = config['loader_id'].split('-')[0]
    loader_name = {'forge': 'Forge', 'neoforge': 'NeoForge', 'fabric': 'Fabric',
                   'quilt': 'Quilt'}.get(family)
    need(loader_name is not None and config['loader_id'].startswith(family + '-'), 'unsupported loader ID')
    need(set(names) == {config['minecraft_version'], loader_name, 'Client'},
         'game_version_names must match Minecraft version, loader and Client')
    need(isinstance(config['reviewed_sha256'], str) and
         re.fullmatch('[0-9a-f]{64}', config['reviewed_sha256']),
         'reviewed_sha256 must identify the manually reviewed export')


def validate(blob, config):
    config_check(config)
    need(len(blob) <= MAX_ZIP, 'ZIP exceeds 90 MiB repository limit')
    digest = hashlib.sha256(blob).hexdigest()
    need(digest == config['reviewed_sha256'], 'ZIP differs from reviewed_sha256')
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        entries = archive.infolist()
        need(0 < len(entries) <= MAX_ENTRIES, 'invalid ZIP entry count')
        need(sum(e.file_size for e in entries) <= MAX_TOTAL, 'expanded ZIP exceeds 256 MiB')
        seen = set()
        manifest = None
        for entry in entries:
            name = entry.filename
            parts = name.rstrip('/').split('/')
            need(name == entry.orig_filename and '\\' not in name and ':' not in name and
                 all(p not in ('', '.', '..') for p in parts) and
                 all(ord(c) >= 32 and ord(c) != 127 for c in name), 'unsafe ZIP path')
            normalized = name.rstrip('/').casefold()
            need(normalized not in seen, 'duplicate ZIP path')
            seen.add(normalized)
            mode = entry.external_attr >> 16
            need(stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR), 'special ZIP entry')
            need(not entry.flag_bits & 1, 'encrypted ZIP entry')
            need(entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'unsupported ZIP compression')
            need(entry.file_size <= MAX_ENTRY and
                 entry.file_size <= max(entry.compress_size, 1) * 200, 'ZIP entry size/ratio limit')
            need(parts[0] == 'overrides' or name in ('manifest.json', 'modlist.html'),
                 'ZIP must have manifest.json, optional modlist.html, and overrides only')
            lower = [p.casefold() for p in parts]
            need(not any(p in DENIED or p.startswith('.') or
                         p.endswith(('.pem', '.key', '.log', '.mca', '.jar', '.zip', '.7z'))
                         for p in lower), 'private/runtime/binary archive content is forbidden')
            if entry.is_dir():
                need(entry.file_size == 0, 'nonempty ZIP directory')
                continue
            need(name != 'overrides', 'overrides must be a directory')
            content = archive.read(entry)  # Verify CRC; never extract.
            if name == 'manifest.json':
                need(len(content) <= 2 * 1024 * 1024, 'manifest too large')
                manifest = parse_json(content)
                # Inspect normalized JSON so escaped keys/values cannot bypass scans.
                canonical = json.dumps(manifest, ensure_ascii=False).encode('utf-8')
                need(not SENSITIVE.search(canonical),
                     'manifest contains a possible credential or connection destination')
            elif name == 'modlist.html':
                try:
                    text = html.unescape(content.decode('utf-8')).encode('utf-8')
                except UnicodeDecodeError:
                    raise Invalid('modlist.html must be UTF-8 text') from None
                # App mod lists contain public project links; no arbitrary URL exemption.
                inspected = PUBLIC_MODLIST_URL.sub(b'', text)
                need(b'\x00' not in text and not SENSITIVE.search(inspected),
                     'modlist contains a possible credential or connection destination')
            elif parts[0] == 'overrides':
                # Conservative first template: only inspectable UTF-8 override files.
                try:
                    content.decode('utf-8')
                except UnicodeDecodeError:
                    raise Invalid('binary overrides require a separately reviewed policy') from None
                need(b'\x00' not in content and not SENSITIVE.search(content),
                     'override contains a possible credential or connection destination')
        need(isinstance(manifest, dict), 'root manifest.json missing or invalid')
        need(any(e.filename == 'overrides/' and e.is_dir() or
                 e.filename.startswith('overrides/') and len(e.filename) > len('overrides/')
                 for e in entries), 'overrides directory missing')
        need(manifest.get('manifestType') == 'minecraftModpack' and
             type(manifest.get('manifestVersion')) is int and manifest['manifestVersion'] == 1,
             'unsupported manifest format')
        need(manifest.get('overrides') == 'overrides', 'unsupported overrides directory')
        for field in ('name', 'version', 'author'):
            need(isinstance(manifest.get(field), str) and manifest[field].strip(), 'manifest identity missing')
        # Keep the former draft name blocked; the current public pack name is
        # valid for App exports, while draft version/author still block previews.
        need(manifest['name'] != 'Create Client Local Draft' and
             not manifest['version'].startswith('0.0.0-local.') and
             manifest['author'] != 'Local assembly (provisional)',
             'local reconstruction draft is not an App export and cannot be submitted')
        minecraft = manifest.get('minecraft')
        need(isinstance(minecraft, dict) and minecraft.get('version') == config['minecraft_version'],
             'Minecraft version differs from export')
        loaders = minecraft.get('modLoaders')
        need(isinstance(loaders, list) and len(loaders) == 1 and isinstance(loaders[0], dict) and
             loaders[0].get('id') == config['loader_id'] and loaders[0].get('primary') is True,
             'loader differs from export (one primary loader required)')
        files = manifest.get('files')
        need(isinstance(files, list) and files, 'manifest files must be a nonempty list')
        ids = set()
        for item in files:
            need(isinstance(item, dict) and positive(item.get('projectID')) and
                 positive(item.get('fileID')) and type(item.get('required')) is bool,
                 'invalid manifest file reference')
            need(item['projectID'] not in ids, 'duplicate project reference')
            ids.add(item['projectID'])
    return digest


def metadata(config, changelog):
    need(changelog.strip() and 'REPLACE_ME' not in changelog and len(changelog.encode()) <= 100000,
         'write a release changelog (up to 100 KB)')
    return {'changelog': changelog, 'changelogType': 'markdown',
            'displayName': config['display_name'], 'releaseType': config['release_type'],
            'gameVersionNames': config['game_version_names'], 'isMarkedForManualRelease': True}


def token_check(token):
    need(token and token.strip() == token and not any(ord(c) < 32 for c in token),
         'CURSEFORGE_API_TOKEN is not configured or invalid')


def submit(blob, config, meta, token, connection_factory=http.client.HTTPSConnection):
    token_check(token)
    # Fixed host, no redirects, proxies, query credentials or retry loop.
    boundary = 'cf-' + uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n'
            'Content-Type: application/json\r\n\r\n').encode() + json.dumps(meta).encode()
    body += (f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; '
             'filename="okd-server-modpack.zip"\r\nContent-Type: application/zip\r\n\r\n').encode()
    body += blob + f'\r\n--{boundary}--\r\n'.encode()
    conn = connection_factory(HOST, timeout=120)
    try:
        conn.request('POST', f"/api/projects/{config['project_id']}/upload-file", body,
                     {'X-Api-Token': token, 'Content-Type': f'multipart/form-data; boundary={boundary}'})
        response = conn.getresponse()
        need(200 <= response.status < 300, 'API did not confirm acceptance; check author dashboard before retrying')
        result = parse_json(response.read(65537))
        need(isinstance(result, dict) and positive(result.get('id')), 'API response missing file ID; check dashboard before retrying')
        return result['id']
    except (OSError, http.client.HTTPException, ValueError):
        raise Invalid('Submission not confirmed. Check author dashboard before any manual retry.') from None
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', required=True)
    parser.add_argument('--config', default='release.json')
    parser.add_argument('--changelog', default='CHANGELOG.md')
    parser.add_argument('--submit', action='store_true', help='actually submit; default is offline dry-run')
    parser.add_argument('--receipt', type=Path, help='write a public JSON submission receipt')
    parser.add_argument('--commit', help='source commit SHA to record with --receipt')
    args = parser.parse_args()
    try:
        path = Path(args.zip)
        need(path.suffix == '.zip' and not path.is_symlink(), 'use a regular export ZIP')
        with path.open('rb') as handle:
            blob = handle.read(MAX_ZIP + 1)
        config = parse_json(Path(args.config).read_text(encoding='utf-8'))
        digest = validate(blob, config)
        meta = metadata(config, Path(args.changelog).read_text(encoding='utf-8'))
        receipt = None
        if args.receipt:
            need(isinstance(args.commit, str) and
                 re.fullmatch(r'[0-9a-f]{40}', args.commit), 'receipt needs a full source commit SHA')
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                manifest = parse_json(archive.read('manifest.json'))
            receipt = {'commit': args.commit, 'version': manifest['version'],
                       'zip_sha256': digest, 'project_id': config['project_id'],
                       'export_asset_id': config['export_asset_id'],
                       'status': 'validated', 'file_id': None}
            # Fail before any network request if the receipt cannot be created.
            with args.receipt.open('x', encoding='utf-8') as handle:
                json.dump(receipt, handle, indent=2)
                handle.write('\n')
        print('Validated SHA256:', digest)
        if args.submit:
            token = os.environ.get('CURSEFORGE_API_TOKEN', '')
            token_check(token)
            # Preserve uncertainty on timeout, malformed replies or runner interruption.
            if receipt is not None:
                receipt['status'] = 'submission_unconfirmed'
                args.receipt.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
            file_id = submit(blob, config, meta, token)
            print(f'API accepted file ID {file_id}; moderation is pending, manual publication required.')
            if receipt is not None:
                receipt.update(status='submitted', file_id=file_id)
                args.receipt.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        else:
            print('DRY RUN: no network request; no file submitted.')
        return 0
    except Invalid as error:
        print('STOP:', error, file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError, NotImplementedError):
        print('STOP: invalid/unreadable input; no successful submission confirmed.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
