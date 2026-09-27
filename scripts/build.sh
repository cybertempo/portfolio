#!/usr/bin/env bash
# Build the site.  [LAPTOP]
#
#   bash scripts/build.sh            validate content/site.toml, render dist/, run the gates
#   bash scripts/build.sh --serve    the same, then preview at http://127.0.0.1:8791/
#
# Requires Python 3.11+ (standard library only). Refuses rather than warns:
# a build that prints "REFUSED" leaves the previous dist/ exactly as it was
# (render.py builds into dist.candidate/ and swaps it in only once every gate
# has passed).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/render.py
if [[ "${1:-}" == "--serve" ]]; then
  exec python3 scripts/serve.py
fi
