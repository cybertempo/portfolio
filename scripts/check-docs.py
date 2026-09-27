#!/usr/bin/env python3
"""Run on the LAPTOP: offline gates for the Portfolio documents.

Checks local links resolve, § references resolve, and no secret-shaped string
is present — in the documents (README, RECOVERY, RULES, Planning). The site's
own content is gated separately and more strictly by scripts/render.py.
Diagnostics never reproduce a matched value.
"""
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = {
    "base64 key body": r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{42,43}=(?![A-Za-z0-9+/=])",
    "SSH public key body": r"AAAAC3NzaC1lZDI1NTE5AAAAI[A-Za-z0-9+/]{30,}",
    "private key header": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "heartbeat credential URL": r"https://hc-ping\.com/[0-9a-f-]{20,}",
    "32-hex token": r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])",
    "Vercel/API token assignment": r"(?i)\b(VERCEL_TOKEN|token|secret|api[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{16,}",
}
LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)")


def sensitive(text):
    return [(name, text.count("\n", 0, m.start()) + 1)
            for name, pattern in PATTERNS.items()
            for m in re.finditer(pattern, text)]


def strip_fences(text):
    return re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", text, flags=re.MULTILINE | re.DOTALL)


def anchors(text):
    found = set()
    for title in re.findall(r"^#{1,6}\s+(.+)$", strip_fences(text), re.MULTILINE):
        slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        found.add(slug)
    return found


def valid_local_target(source, href):
    target = urlsplit(href)
    if target.scheme or target.netloc:
        return True
    p = (source.parent / unquote(target.path)).resolve() if target.path else source
    if p.parent == ROOT / "build" and p.suffix in {".pdf", ".docx"}:
        return (ROOT / "Planning" / (p.stem + ".md")).is_file()
    if not p.exists():
        return False
    if p.is_dir():
        return not target.fragment
    return not target.fragment or (p.suffix == ".md" and unquote(target.fragment) in anchors(p.read_text()))


def check():
    docs = [ROOT / "README.md", ROOT / "RECOVERY.txt", ROOT / "RULES-portfolio.md",
            ROOT / "content" / "topics" / "_README.md", ROOT / "content" / "palettes" / "_README.md",
            *sorted((ROOT / "Planning").glob("*.md"))]
    errors = []
    for p in docs:
        text = p.read_text()
        for kind, line in sensitive(text):
            errors.append(f"{p.relative_to(ROOT)}:{line}: {kind}")
        if p.suffix == ".md":
            for href in LINK.findall(strip_fences(text)):
                if not valid_local_target(p, href):
                    errors.append(f"{p.relative_to(ROOT)}: unresolved local reference")
    rev = (ROOT / "Planning/portfolio-rev1.md").read_text()
    sections = {int(n) for n in re.findall(r"^## (\d+)\.", rev, re.MULTILINE)}
    for reference in re.findall(r"§(\d+)(?![\d.])", rev):
        if int(reference) not in sections:
            errors.append(f"Rev 1: unresolved section reference §{reference}")
    ids = {"F": set(re.findall(r"\| (F\d+) \|", rev)), "D": set(re.findall(r"\| (D\d+) \|", rev)), "Q": set(re.findall(r"\| (Q\d+) \|", rev))}
    for kind, defined in ids.items():
        for used in set(re.findall(rf"\b{kind}\d+\b", rev)):
            if used not in defined:
                errors.append(f"Rev 1: {used} is cited but not defined in its table")
    if errors:
        print("DOCUMENT GATE REFUSED:\n" + "\n".join(errors))
        return 1
    print(f"document gate: {len(docs)} sources checked; links, § references, F/D/Q ids and pattern scan passed")
    return 0


def self_test():
    bad = "A" * 43 + "="
    assert sensitive(bad), "secret-pattern negative control failed"
    assert sensitive("VERCEL_TOKEN=abcdefghijklmnopqrstu"), "token control failed"
    assert not sensitive("the token lives in the CLI's own store, never here"), "positive control failed"
    source = ROOT / "README.md"
    assert valid_local_target(source, "Planning/portfolio-rev1.md")
    assert not valid_local_target(source, "Planning/does-not-exist.md")
    assert valid_local_target(source, "Planning/portfolio-rev1.md#11-open-questions-for-the-owner--and-the-answers")
    assert not valid_local_target(source, "Planning/portfolio-rev1.md#missing-heading")
    print("document gate controls: secret/broken links refused; safe text/valid links passed")


if __name__ == "__main__":
    self_test()
    sys.exit(check())
