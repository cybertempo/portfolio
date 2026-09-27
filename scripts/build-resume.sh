#!/usr/bin/env bash
# Build the published résumé from its LaTeX source, and refuse to publish one
# that carries a phone number.  [LAPTOP]
#
#   bash scripts/build-resume.sh
#
# source/resume/sreenandan-pradeep-resume.tex  ->  src/assets/sreenandan-pradeep-resume.pdf
#
# REGENERATED, NEVER EDITED. The PDF is compiled fresh from the source every
# time: a number removed from the source is absent from the file, not covered
# over, and there is no earlier revision inside it to recover. Then
# check-pdf-private.py reads the new PDF's text, metadata and every string in
# its internals; only a clean result replaces the published copy.
#
# Needs: tectonic (brew install tectonic; on first use it fetches the TeX
# packages this document uses from its bundle server) and Poppler
# (pdftotext, pdfinfo) for the check.
set -euo pipefail
cd "$(dirname "$0")/.."
NAME=sreenandan-pradeep-resume
TEX="source/resume/$NAME.tex"
OUT="src/assets/$NAME.pdf"
[ -f "$TEX" ] || { echo "!!! $TEX is missing"; exit 1; }
command -v tectonic >/dev/null || { echo "!!! tectonic is not installed: brew install tectonic"; exit 1; }
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT

tectonic --outdir "$W" "$TEX"
[ -s "$W/$NAME.pdf" ] || { echo "!!! tectonic produced no PDF"; exit 1; }

# The check must pass on the NEW file before it replaces the published one.
python3 scripts/check-pdf-private.py "$W/$NAME.pdf" \
  || { echo "!!! NOT published: the new PDF failed the privacy check (above)"; exit 1; }

cp "$W/$NAME.pdf" "$OUT"
echo "published: $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes, $(pdfinfo "$OUT" | awk '/^Pages:/{print $2}') page(s))"
echo "next: bash scripts/build.sh   (the site build picks it up), then deploy"
