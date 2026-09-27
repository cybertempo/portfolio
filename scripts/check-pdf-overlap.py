#!/usr/bin/env python3
"""Build gate: refuse a PDF in which text has been drawn on top of other text.
RUNS ON: the laptop (or inside the docs container), as part of build-docs.

WHY (TRAP 4, found 2026-09-16): pandoc wraps every Markdown table in a typst
#figure, and typst 0.15 will not break a figure across pages. A table longer
than the space left on its page had its remaining rows drawn ON TOP OF EACH
OTHER in the last lines of the page - a black smear - and nothing continued on
the next page. Every build reported success. The rows were still in the PDF's
text layer, so `pdftotext | grep` found every one of them: a text-based check
can never fail on this defect. This one is geometric.

WHAT IT MEASURES: pdftotext -bbox gives every word's box. In a correctly laid
out page no two words start at the same point. In the crushed table every
leftover row was drawn from the same origin, so column after column has several
words with identical (x, y). Same-origin pairs are the signature; a clean page
has exactly zero (measured: 0 across every PDF of every project, including the
Chrome-rendered ones), so the threshold is not a tuned number. "Same point" is
the same x and a y within 6 pt - lines of text are never that close, but a
crushed row whose first line is inline code sits ~2.4 pt off its neighbour.
Sensitivity: fires on the FIRST row that outruns the page, then more per row. A long
token that merely spills sideways into the next column overlaps its neighbour
but does not share its origin, and is not flagged here - that is a column-width
problem, visible and harmless, not this trap.

SELF-TEST (RULES 2.2): before judging anything the gate builds two one-table
PDFs with pandoc + typst - one WITHOUT the breakable line (must be refused),
one WITH it (must pass). If it cannot tell them apart it refuses to run, so a
broken instrument never reports a clean document.

  check-pdf-overlap.py [--no-self-test] file.pdf [file.pdf ...]
  exit 0: every file clean.  exit 1: a file is crushed, or the self-test failed.
  exit 2: pdftotext / pandoc / typst missing.
"""
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile

Y_TOL = 6.0   # points; see same_origin_pairs
WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')
PAGE = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', re.S)


def same_origin_pairs(pdf):
    """Per page: list of (word_a, word_b, x, y) drawn from the same point."""
    xml = subprocess.run(['pdftotext', '-bbox', pdf, '-'], capture_output=True, text=True, check=True).stdout
    report = []
    for pno, (_w, _h, body) in enumerate(PAGE.findall(xml), 1):
        # Bucket by x to the half point; within a bucket, two words closer than
        # Y_TOL in y were drawn from the same origin. Lines of real text are
        # 10 pt or more apart, and a crushed row whose first line is inline
        # code lands about 2.4 pt off its neighbour (rev29 41.5), which an
        # exact match missed on 2026-09-16.
        by_x = {}
        for x0, y0, x1, y1, t in WORD.findall(body):
            by_x.setdefault(round(float(x0) * 2), []).append((float(y0), float(x0), html.unescape(t)))
        hits = []
        for column in by_x.values():
            column.sort()
            for (ya, xa, ta), (yb, xb, tb) in zip(column, column[1:]):
                if yb - ya < Y_TOL:
                    hits.append((ta, tb, xa, ya))
        if hits:
            report.append((pno, hits))
    return report


def check(pdf):
    report = same_origin_pairs(pdf)
    total = sum(len(h) for _, h in report)
    if not report:
        print(f"  ok      {os.path.basename(pdf)}: no text drawn over text")
        return True
    print(f"  CRUSHED {os.path.basename(pdf)}: {total} same-origin word pairs")
    for pno, hits in report:
        sample = ', '.join(f"{a!r}/{b!r}" for a, b, _, _ in hits[:4])
        print(f"          page {pno}: {len(hits)} pairs, e.g. {sample}")
    return False


def self_test():
    """Known-bad must be refused, known-good must pass, in the same moment."""
    pandoc, typst = shutil.which('pandoc'), shutil.which('typst')
    if not (pandoc and typst):
        print("check-pdf-overlap: pandoc and typst are needed for the self-test"); return False
    rows = "\n".join(f"| {i} | Row {i} of a table long enough to outrun a page, with text that wraps | note {i} |"
                     for i in range(1, 61))
    md = "# t\n\nbefore\n\n| # | Change | Severity |\n|---|---|---|\n" + rows + "\n\nafter\n"
    with tempfile.TemporaryDirectory(prefix='pdf-overlap-selftest-') as d:
        src = os.path.join(d, 'f.md'); open(src, 'w').write(md)
        results = {}
        for name, header in (('bad', ''), ('good', '#show figure.where(kind: table): set block(breakable: true)\n')):
            typ = os.path.join(d, name + '.typ'); open(typ, 'w').write('#show table.cell.where(y: 0): strong\n' + header)
            out = os.path.join(d, name + '.pdf')
            subprocess.run([pandoc, src, '--pdf-engine=' + typst, '--include-in-header=' + typ, '-o', out],
                           check=True, capture_output=True, timeout=120)
            results[name] = bool(same_origin_pairs(out))
    ok = results['bad'] and not results['good']
    print(f"  self-test: unbreakable table {'REFUSED' if results['bad'] else 'PASSED (!!)'}, "
          f"breakable table {'passed' if not results['good'] else 'REFUSED (!!)'}"
          + ("" if ok else "  -> the instrument is broken; nothing below can be trusted"))
    return ok


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if not shutil.which('pdftotext'):
        print("BUILD ABORTED: pdftotext not found (Mac: brew install poppler; Debian: poppler-utils)."); return 2
    if not args:
        print(__doc__); return 2
    print("=== text drawn over text? (TRAP 4 gate) ===")
    if '--no-self-test' not in argv and not self_test():
        return 1
    return 0 if all([check(p) for p in args]) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
