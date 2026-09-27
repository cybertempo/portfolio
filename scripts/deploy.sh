#!/usr/bin/env bash
# Publish the site.  [LAPTOP]
#
#   bash scripts/deploy.sh
#
# Builds (so nothing stale is ever published), pushes dist/ to Vercel as the
# production deployment, then — if [meta] url is set in content/site.toml —
# proves the live site is byte-for-byte what was built (scripts/verify-live.sh).
#
# One-time setup, by the owner, in a terminal (each may open a browser, which is
# why this script never does it for you):
#   npm install -g vercel        the Vercel CLI (Node.js is already on the laptop)
#   vercel login                 signs the CLI in; the token lives in the CLI's own
#                                store under ~/Library/Application Support, never here
#
# The Vercel project is linked from a cache directory outside the cloud folder
# (RULES 3.5), named after the project so the first deploy creates it by that name.
set -euo pipefail
cd "$(dirname "$0")/.."
source deploy.conf

command -v vercel >/dev/null || { echo "deploy: the Vercel CLI is not installed. In a terminal: npm install -g vercel" >&2; exit 1; }
vercel whoami >/dev/null 2>&1 || { echo "deploy: not signed in to Vercel. In a terminal: vercel login" >&2; exit 1; }

bash scripts/build.sh

stage="${XDG_CACHE_HOME:-$HOME/.cache}/portfolio-deploy/$VERCEL_PROJECT"
mkdir -p "$stage"
rsync -a --delete --exclude .vercel dist/ "$stage/"
echo "deploy: staged dist/ → $stage"

# Bare, not piped: the CLI may ask a question on the very first deploy (RULES 1.3).
vercel deploy --prod --yes --cwd "$stage"

url=$(python3 -c 'import tomllib,sys; print(tomllib.load(open("content/site.toml","rb"))["meta"].get("url",""))')
if [[ -z "$url" ]]; then
  cat <<MSG
deploy: done. The production URL is printed above (https://$VERCEL_PROJECT.vercel.app
        unless a domain was added). Put it in content/site.toml under [meta] url,
        then run this script once more so the page carries its own address and
        the live check below can run.
MSG
  exit 0
fi
bash scripts/verify-live.sh "$url"
