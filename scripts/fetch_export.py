"""Fetch a public same-repository Release asset by ID; validate before saving."""
import argparse
import http.client
from pathlib import Path
import sys
from urllib.parse import urlsplit
import zipfile

from release import Invalid, MAX_ZIP, config_check, need, parse_json, positive, validate

REPOSITORY = 'aiagate/minecraft-modpack-release'
API_HOST = 'api.github.com'
ASSET_HOSTS = {'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}


def get(host, path, accept, limit, connection_factory):
    # GET only; no credentials, proxies, arbitrary hosts or retry loops.
    conn = connection_factory(host, timeout=120)
    try:
        conn.request('GET', path, headers={
            'Accept': accept, 'User-Agent': 'modpack-export-verifier',
            'X-GitHub-Api-Version': '2022-11-28'})
        response = conn.getresponse()
        if response.status == 302:
            return 302, response.getheader('Location'), b''
        need(response.status == 200, 'Release asset GET failed; no export saved')
        body = response.read(limit + 1)
        need(len(body) <= limit, 'Release asset response exceeds local limit')
        return 200, None, body
    except (OSError, http.client.HTTPException, ValueError):
        # Never log API body, a signed redirect URL, or raw exception details.
        raise Invalid('Release asset GET failed; no export saved') from None
    finally:
        conn.close()


def fetch(config, connection_factory=http.client.HTTPSConnection):
    config_check(config)
    asset_id = config['export_asset_id']
    need(positive(asset_id), 'export_asset_id must identify a reviewed public Release asset')
    path = f'/repos/{REPOSITORY}/releases/assets/{asset_id}'
    status, _, raw = get(API_HOST, path, 'application/vnd.github+json',
                         1024 * 1024, connection_factory)
    need(status == 200, 'unexpected metadata redirect')
    asset = parse_json(raw)
    need(isinstance(asset, dict) and type(asset.get('id')) is int and
         asset['id'] == asset_id and asset.get('state') == 'uploaded' and
         positive(asset.get('size')) and asset['size'] <= MAX_ZIP,
         'Release asset ID/state/size mismatch')
    status, location, blob = get(API_HOST, path, 'application/octet-stream',
                                MAX_ZIP, connection_factory)
    if status == 302:
        need(isinstance(location, str), 'Release asset redirect missing')
        url = urlsplit(location)
        need(url.scheme == 'https' and url.hostname in ASSET_HOSTS and
             url.username is None and url.password is None and url.port in (None, 443) and
             not url.fragment and url.path.startswith('/') and
             not any(ord(c) < 32 or ord(c) == 127 for c in location),
             'Release asset redirect is not an allowed GitHub HTTPS destination')
        status, _, blob = get(url.hostname, url.path + ('?' + url.query if url.query else ''),
                              'application/octet-stream', MAX_ZIP, connection_factory)
        need(status == 200, 'multiple Release asset redirects are forbidden')
    need(len(blob) == asset['size'], 'Release asset bytes differ from declared size')
    validate(blob, config)  # Exact reviewed SHA256, privacy, ZIP and manifest checks.
    return blob


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='release.json', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        need(args.output.suffix == '.zip' and not args.output.exists() and
             not args.output.is_symlink(), 'use a new output ZIP path')
        config = parse_json(args.config.read_text(encoding='utf-8'))
        blob = fetch(config)
        with args.output.open('xb') as handle:
            handle.write(blob)
        print('Reviewed export fetched; SHA256:', config['reviewed_sha256'])
        return 0
    except (Invalid, OSError, ValueError, KeyError, TypeError,
            zipfile.BadZipFile, RuntimeError, NotImplementedError):
        print('STOP: invalid/unavailable Release asset; no validated export saved.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
