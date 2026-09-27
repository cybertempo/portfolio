#!/usr/bin/env bash
# Build PDF + DOCX for the PORTFOLIO project documents.  Runs on the LAPTOP (Mac or Linux).
#   bash scripts/build-docs.sh [portfolio-rev1]
# Requires: pandoc, typst, pdftotext (Poppler).
#
# Same pipeline as Monitor/scripts/build-docs.sh and Eye/scripts/build-docs.sh, with
# the four traps those builds paid for (TRAP 1–4 below) and the same overlap gate
# (scripts/check-pdf-overlap.py is byte-identical across projects; keep it so).
# Not wired into Server/Docs/scripts/build-docs.sh for the same reason Monitor and
# Eye are not: that build's first gate compares quoted server config against the
# live server, and this project quotes none.
set -euo pipefail
cd "$(dirname "$0")/.."
SRC=Planning
OUT=build
DOC=${1:-portfolio-rev1}
case "$DOC" in
  portfolio-rev1) TITLE="PORTFOLIO — Rev 1" ;;
  *) echo "Usage: bash scripts/build-docs.sh [portfolio-rev1]"; exit 2 ;;
esac
mkdir -p "$OUT"
# Document gate: links, § references, F/D/Q ids, secret shapes. Refuses; does not warn.
python3 scripts/check-docs.py
# Capture inputs BEFORE rendering (TRAP 3: cloud-folder mtimes are not evidence).
INPUT_STAMP=$(mktemp "${TMPDIR:-/tmp}/portfolio-build.XXXXXX")
trap 'rm -f "$INPUT_STAMP"' EXIT
python3 - > "$INPUT_STAMP" <<'PY'
from pathlib import Path
from hashlib import sha256
paths = [Path(p) for p in ("README.md", "RECOVERY.txt", "RULES-portfolio.md")]
paths += list(Path("Planning").glob("*.md"))
for p in sorted(paths):
    print(f"{sha256(p.read_bytes()).hexdigest()}  {p}")
PY

PANDOC=$(command -v pandoc || true)
[ -n "$PANDOC" ] || { echo "pandoc not found (see the homelab docs-pipeline note: official binary into /usr/local/bin)"; exit 1; }
command -v typst >/dev/null || { echo "typst not found. Run:  brew install typst"; exit 1; }
command -v pdftotext >/dev/null || { echo "pdftotext not found (Poppler) — needed by the overlap gate"; exit 1; }
echo "pandoc : $PANDOC ($("$PANDOC" --version | head -1))"
echo "typst  : $(typst --version)"

# ---- typst preamble ---------------------------------------------------------
cat > "$OUT/header.typ" <<'TYP'
#show heading.where(level: 1): it => { pagebreak(weak: true); it }
#show raw.where(block: true): it => block(
  width: 100%, fill: luma(246), stroke: (left: 2pt + luma(200)),
  inset: (x: 8pt, y: 7pt), radius: 2pt, breakable: true, it
)
#show table.cell.where(y: 0): strong
// TRAP 4: pandoc wraps every table in #figure(), and a figure is NOT breakable.
// A table longer than the space left on the page overprints its remaining rows
// at the page foot and DROPS them from the next page; the PDF looks finished.
#show figure.where(kind: table): set block(breakable: true)
#show table.cell: set align(left)
#show table: set par(justify: false)
#set text(hyphenate: false)
#show "\u{2610}": text(font: "__SYMFONT__")[\u{2610}]
#show "\u{2612}": text(font: "__SYMFONT__")[\u{2612}]
TYP

# ---- TRAP 1 (inherited): a font that carries U+2610; read the list ONCE ------
FONTLIST=$(typst fonts 2>/dev/null || true)
SYMFONT=""
for f in "Apple Symbols" "DejaVu Sans" "Arial Unicode MS" "Noto Sans Symbols 2" "Segoe UI Symbol" "FreeSerif"; do
  if grep -qxF "$f" <<<"$FONTLIST"; then SYMFONT="$f"; break; fi
done
[ -n "$SYMFONT" ] || { echo "BUILD ABORTED: no installed font carries U+2610 (would render as tofu)."; exit 1; }
echo "checkbox font : $SYMFONT"
python3 - "$OUT/header.typ" "$SYMFONT" <<'PY'
import sys, io
p, font = sys.argv[1], sys.argv[2]
s = io.open(p, encoding="utf-8").read()
io.open(p, "w", encoding="utf-8").write(s.replace("__SYMFONT__", font))
PY

# ---- strip the hand-written Contents list; pandoc makes a real one ----------
python3 - "$SRC/$DOC.md" <<'PY'
import io, sys
s = io.open(sys.argv[1], encoding="utf-8").read()
i = s.find("\n## Contents\n")
j = s.find("\n## 0.", i + 1)
if i != -1 and j != -1:
    s = s[:i] + s[j:]
io.open("build/portfolio-print.md", "w", encoding="utf-8").write(s)
print("stripped in-document TOC:", i != -1 and j != -1)
PY

# ---- TRAP 2 (inherited): `margin` must be a MAP, so it comes from a file ----
cat > "$OUT/pdf-meta.yaml" <<'YML'
---
papersize: a4
fontsize: 10pt
margin:
  x: 2.2cm
  y: 2.0cm
---
YML

common=(
  --from=markdown+pipe_tables+backtick_code_blocks+yaml_metadata_block+footnotes+task_lists+lists_without_preceding_blankline
  --toc --toc-depth=2
  --syntax-highlighting=tango
  --resource-path=.
)
pdfopts=( --pdf-engine=typst --include-in-header="$OUT/header.typ" --metadata-file="$OUT/pdf-meta.yaml" )
meta=(
  -M title="$TITLE"
  -M subtitle="The public portfolio site: design, proof, findings, decisions and open questions"
  -M author="Home Lab · Project PORTFOLIO"
  -M date="$(date '+%-d %B %Y')"
)

echo; echo "=== 1/2  $TITLE -> PDF ==="
"$PANDOC" "${common[@]}" "${pdfopts[@]}" "${meta[@]}" "$OUT/portfolio-print.md" -o "$OUT/$DOC.pdf"
echo "=== 2/2  $TITLE -> DOCX ==="
"$PANDOC" "${common[@]}" "${meta[@]}" "$OUT/portfolio-print.md" -o "$OUT/$DOC.docx"
rm -f "$OUT/portfolio-print.md" "$OUT/header.typ" "$OUT/pdf-meta.yaml"

# ---- TRAP 4 gate: no text drawn over text (geometric, self-testing) ---------
if ! python3 ./scripts/check-pdf-overlap.py "$OUT/$DOC.pdf"; then
  rm -f "$OUT/$DOC.pdf"
  echo; echo "BUILD ABORTED: a PDF had text drawn over text (TRAP 4). It has been removed."
  exit 1
fi

# ---- TRAP 3 (inherited): verify by CONTENT HASH, never mtime or du ----------
STAMP="$OUT/.$DOC-sources.sha256"
echo
if ! shasum -a 256 -c "$INPUT_STAMP" >/dev/null 2>&1; then
  echo "BUILD ABORTED: inputs changed during rendering; rerun before using the outputs."; exit 1
fi
for ext in pdf docx; do
  [ -s "$OUT/$DOC.$ext" ] || { echo "BUILD ABORTED: empty $ext output"; exit 1; }
done
cp "$INPUT_STAMP" "$STAMP"
shasum -a 256 "$OUT/$DOC.pdf" "$OUT/$DOC.docx" > "$OUT/.$DOC-outputs.sha256"
python3 - "$OUT/$DOC.pdf" "$OUT/$DOC.docx" <<'PY'
from pathlib import Path
import sys
for name in sys.argv[1:]:
    p = Path(name); print(f"  built   {p.name}: {p.stat().st_size} bytes")
PY
echo "  inputs unchanged during build; source and output hashes recorded"
