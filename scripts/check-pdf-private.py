#!/usr/bin/env python3
"""check-pdf-private.py <file.pdf> - refuse a PDF that carries a phone number.  [LAPTOP]

The published résumé is a public file. The owner's decision (27 Sep 2026) is
that e-mail is the only contact method, so no phone number may be anywhere in
it - not only on the visible page. A number can survive in three places a
reader never sees, and each is checked:

  1. the extractable text      pdftotext, both reading and physical layout
  2. the document metadata     pdfinfo (title, subject, keywords, ...)
  3. every string in the file  the PDF's own string values - link targets
                               (tel:), bookmarks, form fields, the info
                               dictionary - in the raw file and in every
                               decompressed stream, plus any XMP metadata

Only STRING values are read from the file's internals. Streams are mostly
drawing instructions - coordinates, glyph widths, matrices - and matching
digit patterns against those finds "phone numbers" everywhere (the first
version of this checker refused the old résumé twenty times, almost all of
them font-width tables). Page text is pdftotext's job; it decodes glyphs that
a raw scan cannot.

Patterns, not a stored number: this file is public, so it describes the shape
of a phone number and never contains the one it guards against.

Exit 0 clean, 1 a number was found, 2 the PDF could not be read (never "clean").
"""
import re
import shutil
import subprocess
import sys
import zlib

SEP = r"[\s().\- ]"
PATTERNS = {
    "international number": re.compile(r"(?:\+|\b00)\d{1,3}" + SEP + r"*(?:\d" + SEP + r"*){7,}\d"),
    "local number":         re.compile(r"(?<![\d.,])0\d{1,3}" + SEP + r"(?:\d" + SEP + r"?){6,}\d(?![\d.,])"),
    "grouped digit run":    re.compile(r"(?<![\d.,])\d{2,4}(?:" + SEP + r"\d{2,4}){2,}(?![\d.,])"),
    "tel: link":            re.compile(r"\btel:", re.I),
}


def digits(s):
    return sum(ch.isdigit() for ch in s)


def findings(label, text):
    out = []
    for name, rx in PATTERNS.items():
        for m in rx.finditer(text):
            hit = m.group(0)
            # a grouped run is only a phone shape at 9+ digits: dates, scores
            # and counts ("2022 2026", "10 407") are shorter
            if name == "grouped digit run" and digits(hit) < 9:
                continue
            out.append(f"{label}: {name}: {hit.strip()!r}")
    return out


LITERAL = re.compile(rb"\((?:\\.|[^\\()]|\((?:\\.|[^\\()])*\))*\)", re.S)
HEXSTR = re.compile(rb"<([0-9A-Fa-f\s]{4,})>")


def pdf_strings(blob):
    """Every PDF string value in a blob, decoded as far as it will go."""
    out = []
    for m in LITERAL.finditer(blob):
        b = m.group(0)[1:-1]
        b = re.sub(rb"\\([nrtbf()\\])", lambda x: {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"", b"f": b""}.get(x.group(1), x.group(1)), b)
        b = re.sub(rb"\\([0-7]{1,3})", lambda x: bytes([int(x.group(1), 8) & 255]), b)
        out.append(b)
    for m in HEXSTR.finditer(blob):
        h = re.sub(rb"\s", b"", m.group(1))
        if len(h) % 2:
            h += b"0"
        try:
            out.append(bytes.fromhex(h.decode()))
        except ValueError:
            pass
    text = []
    for b in out:
        if b.startswith(b"\xfe\xff"):
            text.append(b[2:].decode("utf-16-be", errors="replace"))
        else:
            text.append(b.decode("latin-1"))
    # pieces of one run of text are often split for kerning, so read them
    # both joined and separated
    return "".join(text) + "\n" + " ".join(text)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {r.stderr.decode(errors='replace').strip()[:200]}")
    return r.stdout.decode("utf-8", errors="replace")


def main():
    if len(sys.argv) != 2:
        print(__doc__.splitlines()[0]); return 2
    pdf = sys.argv[1]
    for tool in ("pdftotext", "pdfinfo"):
        if not shutil.which(tool):
            print(f"COULD NOT CHECK: {tool} is not installed (Poppler)"); return 2
    try:
        raw = open(pdf, "rb").read()
        if not raw.startswith(b"%PDF-"):
            print("COULD NOT CHECK: not a PDF"); return 2
        text_reading = run(["pdftotext", "-enc", "UTF-8", pdf, "-"])
        text_layout = run(["pdftotext", "-layout", "-enc", "UTF-8", pdf, "-"])
        meta = run(["pdfinfo", "-enc", "UTF-8", pdf])
    except (OSError, RuntimeError) as e:
        print(f"COULD NOT CHECK: {e}"); return 2
    if len(text_reading.strip()) < 200:
        # a positive control on the instrument: a résumé with almost no
        # extractable text means extraction failed, not that it is clean
        print("COULD NOT CHECK: almost no text could be extracted"); return 2

    streams = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S):
        body = m.group(1)
        try:
            streams.append(zlib.decompress(body))
        except zlib.error:
            streams.append(body)

    found = []
    found += findings("text", text_reading)
    found += findings("text (layout)", text_layout)
    found += findings("metadata", meta)
    found += findings("strings in the file", pdf_strings(raw))
    for i, s in enumerate(streams):
        found += findings(f"strings in stream {i}", pdf_strings(s))
        if b"<x:xmpmeta" in s:
            found += findings(f"XMP metadata (stream {i})", re.sub(r"<[^>]+>", " ", s.decode("utf-8", errors="replace")))

    if found:
        print("REFUSED - a phone number is in this PDF:")
        for f in sorted(set(found), key=lambda x: (not x.startswith("text"), x))[:20]:
            print("   ", f)
        return 1
    print(f"clean: no phone number in the text, the metadata, or the strings of the file and its {len(streams)} decompressed stream(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
