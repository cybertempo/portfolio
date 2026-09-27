#!/usr/bin/env python3
"""[LAPTOP] Verify every public file and exact security headers against dist/.

Invoked by verify-live.sh (and therefore every deploy). Python standard library
plus curl; four read-only requests at a time, bounded network timeouts. The
local build is the reference, never a manifest fetched from the public site.
"""
from concurrent.futures import ThreadPoolExecutor
from email.parser import Parser
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import tomllib
from urllib.parse import quote, urlsplit
from uuid import uuid4

import render


class Failed(Exception):
    pass


def request(url):
    with TemporaryDirectory(prefix='portfolio-verify-') as tmp:
        body, headers = Path(tmp) / 'body', Path(tmp) / 'headers'
        result = subprocess.run([
            'curl', '--silent', '--show-error', '--connect-timeout', '10',
            '--max-time', '30', '--proto', '=https,http',
            '--header', 'Cache-Control: no-cache', '--dump-header', str(headers),
            '--output', str(body), '--write-out', '%{http_code}', url,
        ], capture_output=True, text=True, timeout=35)
        if result.returncode:
            raise Failed('network/TLS request failed')
        status = int(result.stdout)
        # Ignore interim/proxy CONNECT headers. Inspect the actual response.
        blocks = headers.read_text().strip().split('\n\n')
        final = next((b for b in reversed(blocks) if b.startswith('HTTP/')), '')
        parsed = Parser().parsestr(final.partition('\n')[2])
        return status, {k.lower(): ', '.join(parsed.get_all(k)) for k in parsed}, body.read_bytes()


def verify_response(response, digest, expected_headers):
    status, headers, body = response
    if status != 200:
        raise Failed(f'expected HTTP 200, received {status}')
    if sha256(body).hexdigest() != digest:
        raise Failed('content differs from the local build')
    for name, expected in expected_headers.items():
        if headers.get(name.lower()) != expected:
            raise Failed(f'{name} missing or different from the configured value')


def verify_absent(status):
    if status != 404:
        raise Failed(f'expected HTTP 404, received {status}')


def controls():
    """Prove good content passes and altered bytes, headers and errors fail."""
    body = b'control: ordinary public content'
    digest = sha256(body).hexdigest()
    headers = {'content-security-policy': render.CSP}
    verify_response((200, headers, body), digest, headers)
    for fixture in ((200, headers, body + b'changed'),
                    (200, {'content-security-policy': "default-src *"}, body),
                    (200, {}, body), (500, headers, body)):
        try:
            verify_response(fixture, digest, headers)
        except Failed:
            pass
        else:
            raise Failed('verification control failed to reject a bad response')
    verify_absent(404)
    for status in (0, 200, 301, 403, 500):
        try:
            verify_absent(status)
        except Failed:
            pass
        else:
            raise Failed('404 control accepted an error, redirect or live page')
    print('controls: valid content/404 passed; altered content, weak headers and HTTP errors refused')


def main():
    controls()
    if sys.argv[1:] == ['--self-test']:
        return
    config = tomllib.loads(render.CONTENT.read_text())
    url = (sys.argv[1] if len(sys.argv) > 1 else config['meta'].get('url', '')).rstrip('/')
    target = urlsplit(url)
    if target.scheme != 'https' and not (target.scheme == 'http' and target.hostname in ('127.0.0.1', 'localhost', '::1')):
        raise Failed('use HTTPS (HTTP allowed only for a loopback preview)')
    manifest = json.loads((render.DIST / '.build.json').read_text())
    files = manifest.get('files', {})
    if not files or files != render.public_files():
        raise Failed('manifest is incomplete or local files changed; rebuild first')
    if files.get('index.html') != manifest.get('index_sha256'):
        raise Failed('manifest index hash is inconsistent')
    expected_headers = dict(render.HEADERS)
    host_headers = json.loads((render.DIST / 'vercel.json').read_text())['headers'][0]['headers']
    if {h['key']: h['value'] for h in host_headers} != expected_headers:
        raise Failed('generated host headers are stale; rebuild first')
    failures = []

    def verify_file(item):
        name, digest = item
        route = '/' if name == 'index.html' else '/' + quote(name, safe='/')
        try:
            verify_response(request(url + route), digest, expected_headers)
            return None
        except (Failed, OSError, ValueError, subprocess.TimeoutExpired) as error:
            return f'{name}: {error}'

    with ThreadPoolExecutor(max_workers=4) as pool:
        for failure in pool.map(verify_file, files.items()):
            if failure:
                failures.append(failure)
    if failures:
        raise Failed('\n'.join(failures))
    print(f'  ok    all {len(files)} public pages/assets match the local build')
    print(f'  ok    all {len(expected_headers)} security header values match on every file')
    index = (render.DIST / 'index.html').read_text()
    if 'Sreenandan Pradeep' not in index or render.scan_name(index):
        raise Failed('name gate failed')
    print('  ok    name gate on the verified live content')
    # Read-only checks: no uploads, writes or destructive requests to production.
    for path in (f'no-such-page-{uuid4().hex}', '.env', '.git/config',
                 'content/site.toml', 'scripts/deploy.sh'):
        try:
            verify_absent(request(url + '/' + path)[0])
        except Failed as error:
            raise Failed(f'{path}: {error}') from error
    print('  ok    unknown path and checked private/source paths return 404')
    print(f'verify-live: PASS — {url} matches the complete local build')


if __name__ == '__main__':
    try:
        main()
    except (Failed, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        print(f'verify-live: FAIL — {error}', file=sys.stderr)
        sys.exit(1)
