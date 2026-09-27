#!/usr/bin/env bash
# Fetch the two typefaces as woff2 so the site serves them itself.  [LAPTOP]
#
# Why: a <link> to fonts.googleapis.com sends every visitor's IP address and
# browser to Google on every page view. Serving the files ourselves means the
# page makes no third-party request at all, and works offline.
#
# All three faces (JetBrains Mono, Space Grotesk, Chakra Petch) are under the SIL Open Font License 1.1 (redistribution permitted).
# Run once, and again only to change the weights below. Output is committed
# under src/assets/fonts/ and is an input to the build, not a build product.
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=src/assets/fonts
mkdir -p "$DEST"
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'
CSS_URL='https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300..800&family=Space+Grotesk:wght@300..700&family=Chakra+Petch:wght@700&display=swap'

css=$(curl -fsS -A "$UA" "$CSS_URL")
: > "$DEST/fonts.css"
# Keep only the latin subset blocks; rewrite each remote url() to a local file.
CSS="$css" python3 - "$DEST" <<'PY'
import re, sys, os, subprocess, pathlib
dest = pathlib.Path(sys.argv[1]); css = os.environ["CSS"]
# Google serves either one variable file per family (repeated for every requested
# weight) or one static file per weight. Handle both: collect (family, weight) → url.
faces = {}
for subset, block in re.findall(r'/\* (\w+) \*/\s*(@font-face \{.*?\})', css, re.S):
    if subset != 'latin': continue
    fam = re.search(r"font-family: '([^']+)'", block).group(1)
    w = re.search(r'font-weight: (\d+(?: \d+)?)', block).group(1)
    url = re.search(r'url\((https://[^)]+)\)', block).group(1)
    faces.setdefault(fam, {})[w] = url
out = []
for fam, byw in faces.items():
    stem = fam.replace(' ', '')
    if len(set(byw.values())) == 1:                       # variable: one file, a weight range
        fname = stem + '.woff2'
        subprocess.run(['curl', '-fsS', '-o', str(dest / fname), next(iter(byw.values()))], check=True)
        out.append(f"@font-face {{\n  font-family: '{fam}';\n  font-style: normal;\n  font-weight: 300 800;\n  font-display: swap;\n  src: url({fname}) format('woff2');\n}}")
        print(f'fetch-fonts: {fname} variable ({(dest / fname).stat().st_size // 1024} KB)')
    else:                                                  # static: one file per weight
        for w, url in sorted(byw.items()):
            fname = f'{stem}-{w}.woff2'
            subprocess.run(['curl', '-fsS', '-o', str(dest / fname), url], check=True)
            out.append(f"@font-face {{\n  font-family: '{fam}';\n  font-style: normal;\n  font-weight: {w};\n  font-display: swap;\n  src: url({fname}) format('woff2');\n}}")
            print(f'fetch-fonts: {fname} ({(dest / fname).stat().st_size // 1024} KB)')
(dest / 'fonts.css').write_text('\n'.join(out) + '\n')
PY
ls -la "$DEST"
