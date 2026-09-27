#!/usr/bin/env python3
"""Render the portfolio: content/site.toml + src/ → dist/.   [LAPTOP]

Run through scripts/build.sh. Standard library only (Python ≥ 3.11).

What it does, in order:
  1. loads and validates content/site.toml — an invalid field refuses the
     whole render; nothing is produced half-right (RULES 3.3);
  2. fire-tests every gate against a synthetic bad fixture, so a gate that
     has silently stopped working fails the build (RULES 2.2);
  3. renders src/index.html with the content, copies src/ static files,
     writes the host header files (one header set, two formats);
  4. runs the gates over dist/: no secret-shaped string, no forbidden name,
     no external script/style/font/image, every local asset present;
  5. prints a report: hidden links (empty urls) and the output hash, and
     writes dist/.build.json for scripts/verify-live.sh.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "site.toml"
SRC = ROOT / "src"
DIST = ROOT / "dist"
TONES = ("primary", "secondary", "tertiary", "success", "warning", "danger", "muted")
BADGE_TONES = TONES[:6]
TOPICS = ROOT / "content" / "topics"
PALETTES = ROOT / "content" / "palettes"
PALETTE_KEYS = ("bg", "bg2", "panel", "panel2", "text", "muted", "faint", "stroke",
                "primary", "secondary", "tertiary", "success", "warning", "danger")
TEXT_SUFFIXES = {".html", ".css", ".js", ".json", ".svg", ".txt", ".toml", ".md"}


class Refuse(SystemExit):
    def __init__(self, msg: str):
        super().__init__(f"render: REFUSED — {msg}")


# ── the header set: defined once, emitted in every format a host reads ──────
CSP = ("default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
       "font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; "
       "require-trusted-types-for 'script'; trusted-types 'none'; "
       "upgrade-insecure-requests")
# frame-ancestors is enforced by the HTTP header, not supported in a meta tag.
META_CSP = CSP.replace("frame-ancestors 'none'; ", "")
HEADERS = [
    ("Content-Security-Policy", CSP),
    ("Strict-Transport-Security", "max-age=63072000; includeSubDomains"),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
    ("Permissions-Policy", "camera=(), microphone=(), geolocation=(), interest-cohort=()"),
    ("Cross-Origin-Opener-Policy", "same-origin"),
    ("Cross-Origin-Resource-Policy", "same-origin"),
]

# ── gates ───────────────────────────────────────────────────────────────────
SECRET_PATTERNS = {
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "OpenAI/Anthropic-style key": re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    "password/token assignment": re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"]?[^\s'\"<]{8,}"),
    "long hex string": re.compile(r"(?<![A-Za-z0-9])[0-9a-f]{40,}(?![A-Za-z0-9])"),
}
# The owner's first name is Sreenandan. The shortened form must never appear
# on its own — "Sreenandan" contains it, so a lookbehind excludes that.
FORBIDDEN_NAME = re.compile(r"(?i)(?<![a-z])nandan(?![a-z])")
# Anything the browser would fetch from another origin. Visitor-facing <a href>
# links are allowed; resources are not.
EXTERNAL_RESOURCE = re.compile(
    r"(?i)(?:<(?:script|link|img|source|iframe|video|audio|object|embed)\b[^>]*?\b(?:src|href)\s*=\s*['\"]?\s*(?:https?:)?//)"
    r"|(?:url\(\s*['\"]?\s*(?:https?:)?//)"
    r"|(?:@import\s+['\"]?\s*(?:https?:)?//)"
    r"|(?:\bfetch\s*\(|\bnew\s+XMLHttpRequest\b|\bnavigator\.sendBeacon\b|\bimport\s*\(\s*['\"](?:https?:)?//)"
)


def scan_secrets(text: str) -> str | None:
    for name, rx in SECRET_PATTERNS.items():
        if rx.search(text):
            return name
    return None


def scan_name(text: str) -> bool:
    return bool(FORBIDDEN_NAME.search(text))


# <link rel="canonical"> names the page's own public address; the browser fetches nothing from it.
CANONICAL_LINK = re.compile(r'<link\s+rel="canonical"[^>]*>')


def scan_external(text: str) -> bool:
    return bool(EXTERNAL_RESOURCE.search(CANONICAL_LINK.sub("", text)))


def fire_test_gates() -> None:
    """Each gate must refuse a synthetic bad input and pass a clean one."""
    bad_secrets = {
        # Built at run time, never written whole: a public repository's secret
        # scanner would otherwise flag this file for the fixtures that prove
        # the gate works (27 Sep 2026).
        "private key block": "-----BEGIN RSA " + "PRIVATE KEY-----",
        "AWS access key": "AKIA" + "IOSFODNN7EXAMPLE",
        "OpenAI/Anthropic-style key": "sk-" + "ant-abcdefghijklmnopqrstuvwxyz0123",
        "GitHub token": "ghp_" + "a" * 36,
        "JWT": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.abcdefghijklmnop",
        "password/token assignment": "password = hunter22222",
        "long hex string": "d" * 40,
    }
    for name, fixture in bad_secrets.items():
        if scan_secrets(fixture) != name:
            raise Refuse(f"secret gate broken: '{name}' pattern did not catch its fixture")
    clean = "password for sreenandan: ********  AIR 5691 of 170,825  https://example.org/x"
    if scan_secrets(clean):
        raise Refuse(f"secret gate broken: false positive on clean fixture ({scan_secrets(clean)})")

    if not scan_name("root@nandan:~$") or not scan_name("Nandan is here") or not scan_name("[sudo] password for nandan:"):
        raise Refuse("name gate broken: did not catch the standalone name")
    if scan_name("Sreenandan Pradeep sreenandan_pradeep sreenandan@portfolio"):
        raise Refuse("name gate broken: false positive on the full name")

    bad_ext = [
        '<link href="https://fonts.googleapis.com/css2" rel="stylesheet">',
        '<link rel="stylesheet" href="https://x.test/a.css">',
        '<link rel="canonical" href="https://x.test/"><link rel="stylesheet" href="https://x.test/a.css">',
        "<script src='//cdn.example.com/x.js'></script>",
        "background:url(https://x.test/a.png)",
        "@import 'https://x.test/a.css';",
        "fetch('https://api.example.com')",
        '<img src="http://x.test/a.png">',
    ]
    for f in bad_ext:
        if not scan_external(f):
            raise Refuse(f"external-resource gate broken: did not catch {f!r}")
    clean_ext = '<a href="https://github.com/x">GitHub</a> url(assets/fonts/x.woff2) <img src="assets/p.webp"> <link rel="canonical" href="https://example.org/">'
    if scan_external(clean_ext):
        raise Refuse("external-resource gate broken: false positive on local references")
    print("gate: fire tests      ok (secrets ×%d, name, external resources)" % len(bad_secrets))


# ── the photo ───────────────────────────────────────────────────────────────
def webp_size(path: Path) -> tuple[int, int]:
    """Width and height of a WebP (VP8X, VP8L or simple VP8) or PNG, standard library only."""
    b = path.read_bytes()[:64]
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
    if b[:4] != b"RIFF" or b[8:12] != b"WEBP":
        raise Refuse(f"{path.name}: not a WebP or PNG file")
    chunk = b[12:16]
    if chunk == b"VP8X":
        return int.from_bytes(b[24:27], "little") + 1, int.from_bytes(b[27:30], "little") + 1
    if chunk == b"VP8L":
        bits = int.from_bytes(b[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8 ":
        return int.from_bytes(b[26:28], "little") & 0x3FFF, int.from_bytes(b[28:30], "little") & 0x3FFF
    raise Refuse(f"{path.name}: unknown WebP layout {chunk!r}")


def ensure_photo(name: str, keep_top: float = 1.0) -> None:
    """src/assets/<name> must exist. If source/<stem>.png exists it is the
    master: derive the web image from it whenever its content hash differs
    from the one recorded at the last derivation (timestamps are unreliable
    in a cloud-synced folder, so a hash is used)."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.(webp|png)", name):
        raise Refuse(f"identity.photo: {name!r} must be a .webp or .png file name under src/assets/")
    dest = SRC / "assets" / name
    master = ROOT / "source" / (Path(name).stem + ".png")
    if master.is_file():
        want = hashlib.sha256(master.read_bytes() + f"keep-top={keep_top}".encode()).hexdigest()
        sidecar = dest.with_name(dest.name + ".src-sha256")
        have = sidecar.read_text().strip() if sidecar.is_file() else ""
        if not dest.is_file() or have != want:
            print(f"photo: source/{master.name} changed — deriving src/assets/{name}")
            subprocess.run([sys.executable, str(ROOT / "scripts" / "build-photo.py"), str(master), str(keep_top)], check=True)
    if not dest.is_file():
        raise Refuse(f"identity.photo: src/assets/{name} does not exist and there is no source/{master.name} to derive it from")


# ── palette ─────────────────────────────────────────────────────────────────
def load_palette(name: str) -> dict:
    if not re.fullmatch(r"[a-z0-9-]+", name):
        raise Refuse(f"design.palette: {name!r} must be lowercase letters, digits and hyphens (a file in content/palettes/)")
    f = PALETTES / f"{name}.toml"
    if not f.is_file():
        raise Refuse(f"design.palette: content/palettes/{name}.toml does not exist; available: "
                     + ", ".join(p.stem for p in sorted(PALETTES.glob("*.toml"))))
    try:
        pal = tomllib.loads(f.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise Refuse(f"palettes/{name}.toml does not parse: {e}")
    for k in PALETTE_KEYS:
        v = pal.get(k)
        if not isinstance(v, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
            raise Refuse(f"palettes/{name}.toml: '{k}' must be a #rrggbb colour, got {v!r}")
    return pal


def load_minimap(name: str) -> dict[str, str]:
    """Each minimap is a self-contained, palette-driven front-end module."""
    if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
        raise Refuse("design.minimap: use a lowercase folder name under src/minimaps/")
    folder = SRC / "minimaps" / name
    files = ("template.html", "style.css", "behavior.js")
    if any(not (folder / f).is_file() for f in files):
        raise Refuse(f"design.minimap: {name!r} must contain template.html, style.css and behavior.js")
    result = {f: (folder / f).read_text(encoding="utf-8") for f in files}
    for f, text in result.items():
        if not text.strip() or scan_secrets(text) or scan_name(text) or scan_external(text):
            raise Refuse(f"minimaps/{name}/{f}: empty or failed source safety checks")
    if "{{rail_stops}}" not in result["template.html"]:
        raise Refuse(f"minimaps/{name}/template.html: missing section stops placeholder")
    return result


def palette_css(pal: dict) -> str:
    def rgb(h: str) -> str:
        return ",".join(str(int(h[i:i + 2], 16)) for i in (1, 3, 5))
    lines = [f"  --{k}:{pal[k]}; --{k}-rgb:{rgb(pal[k])};" for k in PALETTE_KEYS]
    lines += ["  --accent:var(--primary); --accent-rgb:var(--primary-rgb);",
              "  --line:rgba(var(--secondary-rgb),.22); --line-strong:rgba(var(--primary-rgb),.6);"]
    return "/* generated by render.py from content/palettes/ — edit the palette, not this */\n:root{\n" + "\n".join(lines) + "\n}\n"


def favicon_svg(pal: dict) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="{pal["bg"]}"/>'
            f'<text x="10" y="44" font-family="JetBrains Mono,Menlo,monospace" font-size="34" font-weight="800" fill="{pal["primary"]}">&gt;_</text></svg>\n')


# ── icons: inline SVG line figures in palette colours (no emoji: emoji come from
#    the OS font and ignore the palette). Stroke is currentColor. ────────────
ICONS = {
    "trophy": '<path d="M7 4h10v5a5 5 0 0 1-10 0V4z"/><path d="M7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3"/><path d="M12 14v3M8 20h8M10 17h4v3h-4z"/>',
    "medal": '<circle cx="12" cy="15" r="5"/><path d="M12 12.5v5M9.8 15h4.4"/><path d="M8.5 10.5 6 3h4l2 5 2-5h4l-2.5 7.5"/>',
    "star": '<path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1.1 5.9L12 16.9l-5.3 2.8 1.1-5.9-4.3-4.1 5.9-.8z"/>',
    "certificate": '<rect x="3" y="5" width="18" height="13" rx="1.5"/><path d="M7 9h10M7 12h6"/><circle cx="16.5" cy="15" r="2"/><path d="M15.5 17v4l1-1 1 1v-4"/>',
    "bolt": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "flag": '<path d="M5 21V4M5 4h13l-3 4 3 4H5"/>',
    "envelope": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    "pen": '<path d="m4 20 1-4L16.5 4.5a2.1 2.1 0 0 1 3 3L8 19z"/><path d="m14 7 3 3"/>',
    "git": '<circle cx="6" cy="6" r="2.2"/><circle cx="6" cy="18" r="2.2"/><circle cx="18" cy="8" r="2.2"/><path d="M6 8.2v7.6M18 10.2c0 4-4 4-8 5.2"/>',
    "external": '<path d="M14 4h6v6M20 4l-9 9"/><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>',
    "document": '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5M10 12h6M10 16h6"/>',
    "play": '<path d="M7 4v16l13-8z"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
}
# which icon a link button gets, by its label (lowercased); anything else gets "link"
LINK_ICONS = {"github": "git", "gitlab": "git", "source": "git", "code": "git", "live": "external", "demo": "external",
              "site": "external", "linkedin": "external", "x": "external", "twitter": "external", "docs": "document",
              "paper": "document", "report": "document", "trailer": "play", "video": "play"}


def icon(name: str, cls: str = "ico") -> str:
    if name not in ICONS:
        raise Refuse(f"unknown icon {name!r}; available: {', '.join(sorted(ICONS))}")
    return (f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')


def link_icon(label: str) -> str:
    return icon(LINK_ICONS.get(label.strip().lower(), "link"))


# ── markup ──────────────────────────────────────────────────────────────────
TONE_RX = re.compile(r"\{(" + "|".join(TONES) + r")\}(.*?)\{/\}", re.S)
# **bold** — the content must not itself be asterisks, so a literal run like
# "********" (a masked password) is left alone.
BOLD_RX = re.compile(r"(?<!\*)\*\*(?=[^*\s])([^*]+?)(?<=[^*\s])\*\*(?!\*)", re.S)
BARE_BOLD = re.compile(r"(?<!\*)\*\*(?!\*)")


def markup(s: str, where: str) -> str:
    """Escape, then apply the tiny allowed markup. Unbalanced markup refuses."""
    if not isinstance(s, str):
        raise Refuse(f"{where}: expected text, got {type(s).__name__}")
    out = html.escape(s, quote=True)
    out = TONE_RX.sub(lambda m: f'<span class="t-{m.group(1)}">{m.group(2)}</span>', out)
    out = BOLD_RX.sub(r"<b>\1</b>", out)
    if re.search(r"\{(?:" + "|".join(TONES) + r"|/)\}", out) or BARE_BOLD.search(out):
        raise Refuse(f"{where}: unbalanced markup in {s!r}")
    return out


def plain(s: str, where: str) -> str:
    """Escaped text with no markup allowed (attributes, titles)."""
    if not isinstance(s, str) or not s.strip():
        raise Refuse(f"{where}: must be non-empty text")
    if "**" in s or "{" in s:
        raise Refuse(f"{where}: markup is not allowed here ({s!r})")
    return html.escape(s, quote=True)


# ── validation ──────────────────────────────────────────────────────────────
def need(d: dict, key: str, where: str, typ=str):
    if key not in d:
        raise Refuse(f"{where}: missing '{key}'")
    v = d[key]
    if typ is str and (not isinstance(v, str) or not v.strip()):
        raise Refuse(f"{where}.{key}: must be non-empty text")
    if typ is list and (not isinstance(v, list) or not v):
        raise Refuse(f"{where}.{key}: must be a non-empty list")
    if typ is dict and not isinstance(v, dict):
        raise Refuse(f"{where}.{key}: must be a table")
    return v


def check_url(u: str, where: str, allow_empty=True) -> str:
    if u == "" and allow_empty:
        return ""
    if not re.fullmatch(r"https://[^\s\"'<>]+", u):
        raise Refuse(f"{where}: url must start with https:// (or be \"\" to hide it), got {u!r}")
    return u


def check_email(e: str, where: str) -> tuple[str, str]:
    m = re.fullmatch(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", e)
    if not m:
        raise Refuse(f"{where}: not an e-mail address: {e!r}")
    return m.group(1), m.group(2)


# ── fragments ───────────────────────────────────────────────────────────────
def chips(items: list, where: str, topics: dict | None, unlinked: list[str]) -> str:
    """A list of chips. With `topics` (chip text → slug), each chip that has an
    explainer becomes a link to it; chips without one are plain and recorded
    in `unlinked` for the build report. topics=None means never link."""
    if not items or not all(isinstance(i, str) and i.strip() for i in items):
        raise Refuse(f"{where}: items must be non-empty strings")
    out = []
    for i in items:
        slug = topics.get(i.lower()) if topics is not None else None
        if slug:
            out.append(f'<li><a class="chip" href="topics/{slug}.html" target="_blank" rel="noopener">{plain(i, where)}</a></li>')
        else:
            if topics is not None:
                unlinked.append(i)
            out.append(f'<li class="chip">{plain(i, where)}</li>')
    return '<ul class="chips">' + "".join(out) + "</ul>"


# ── topics (explainer pages) ────────────────────────────────────────────────
def load_topics() -> tuple[dict, dict]:
    """Returns (by_slug: slug → topic dict, lookup: lowercased name/alias → slug)."""
    by_slug, lookup = {}, {}
    for f in sorted(TOPICS.glob("*.toml")):
        w = f"topics/{f.name}"
        if not re.fullmatch(r"[a-z0-9-]+\.toml", f.name):
            raise Refuse(f"{w}: file name must be lowercase letters, digits and hyphens")
        try:
            tp = tomllib.loads(f.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            raise Refuse(f"{w}: does not parse: {e}")
        slug = f.stem
        need(tp, "name", w); need(tp, "tagline", w); need(tp, "pro", w, list); need(tp, "noob", w, list)
        d = need(tp, "diagram", w, dict)
        if need(d, "kind", w + ".diagram") not in ("flow", "stack", "hub"):
            raise Refuse(f"{w}.diagram.kind: must be flow, stack or hub")
        items = need(d, "items", w + ".diagram", list)
        if len(items) < 2 or any(len(i) > 26 for i in items):
            raise Refuse(f"{w}.diagram.items: 2+ labels of at most 26 characters")
        need(d, "caption", w + ".diagram")
        for key in (tp["name"], *tp.get("aliases", [])):
            k = key.lower()
            if k in lookup and lookup[k] != slug:
                raise Refuse(f"{w}: '{key}' is already claimed by topics/{lookup[k]}.toml")
            lookup[k] = slug
        by_slug[slug] = tp
    return by_slug, lookup


def svg_diagram(kind: str, items: list[str], where: str) -> str:
    """A small themed SVG. Widths come from label length; classes are styled in style.css."""
    def box(x, y, w, h, label, cls="dg-box"):
        return (f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="6"/>'
                f'<text class="dg-label" x="{x + w / 2:.0f}" y="{y + h / 2 + 4:.0f}" text-anchor="middle">{html.escape(label)}</text>')
    ch, pad, h = 7.4, 22, 40          # approx px per character at 12px mono; box padding; box height
    if kind == "flow":
        gap = 34
        widths = [max(80, int(len(i) * ch + pad)) for i in items]
        total = sum(widths) + gap * (len(items) - 1)
        x, parts = 0, []
        for idx, (w, label) in enumerate(zip(widths, items)):
            arrow_label = label.strip() in ("hash →", "→")
            if arrow_label:   # an item that is itself an arrow label: draw as text over the gap
                parts.append(f'<text class="dg-label dg-muted" x="{x + w / 2:.0f}" y="{h / 2 - 2:.0f}" text-anchor="middle">{html.escape(label)}</text>')
            else:
                parts.append(box(x, 0, w, h, label, "dg-box dg-first" if idx == 0 else ("dg-box dg-last" if idx == len(items) - 1 else "dg-box")))
            if idx < len(items) - 1:
                parts.append(f'<path class="dg-arrow" marker-end="url(#ah)" d="M{x + w + 4} {h / 2} L{x + w + gap - 6} {h / 2}"/>')
            x += w + gap
        defs = '<defs><marker id="ah" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path class="dg-head" d="M0 0 L8 4 L0 8 z"/></marker></defs>'
        return f'<svg class="dg" viewBox="-2 -6 {total + 4} {h + 8}" role="img" aria-label="{html.escape(" → ".join(items))}">{defs}{"".join(parts)}</svg>'
    if kind == "stack":
        w = max(max(len(i) for i in items) * ch + pad * 2, 240)
        gap, parts = 10, []
        for idx, label in enumerate(items):
            parts.append(box(0, idx * (h + gap), w, h, label, "dg-box dg-first" if idx == 0 else ("dg-box dg-last" if idx == len(items) - 1 else "dg-box")))
        total_h = len(items) * (h + gap) - gap
        return f'<svg class="dg dg-stack" viewBox="-2 -2 {w + 4:.0f} {total_h + 4}" role="img" aria-label="{html.escape(" over ".join(items))}">{"".join(parts)}</svg>'
    # hub
    centre, spokes = items[0], items[1:]
    cw = max(140, int(len(centre) * ch + pad * 2)); cx_, cy_ = 300, 130
    parts = []
    n = len(spokes)
    import math
    for idx, label in enumerate(spokes):
        ang = -math.pi / 2 + idx * 2 * math.pi / n
        rx, ry = 230, 95
        x, y = cx_ + rx * math.cos(ang), cy_ + ry * math.sin(ang)
        w = max(80, int(len(label) * ch + pad))
        parts.append(f'<path class="dg-spoke" d="M{cx_} {cy_} L{x:.0f} {y:.0f}"/>')
        parts.append(box(x - w / 2, y - h / 2 + 2, w, h - 4, label))
    parts.append(box(cx_ - cw / 2, cy_ - h / 2, cw, h, centre, "dg-box dg-first"))
    return f'<svg class="dg" viewBox="0 0 600 {cy_ * 2}" role="img" aria-label="{html.escape(centre)} connected to {html.escape(", ".join(spokes))}">{"".join(parts)}</svg>'


def render_topics(by_slug: dict, used_in: dict, common: dict) -> dict[str, str]:
    """slug → page html. used_in: slug → [(project title, idx)]."""
    tpl = (SRC / "topic.html").read_text(encoding="utf-8")
    pages = {}
    for slug, tp in by_slug.items():
        w = f"topics/{slug}.toml"
        uses = used_in.get(slug, [])
        used_html = ""
        if uses:
            items = "".join(f'<li><a href="../index.html#projects">{plain(t, w)}</a></li>' for t in uses)
            used_html = f'  <section class="used-in"><h2>Where I\'ve used it</h2><ul>{items}</ul></section>'
        d = tp["diagram"]
        values = {**common, "csp": html.escape(META_CSP, quote=True),
                  "slug": slug, "name": plain(tp["name"], w), "tagline": markup(tp["tagline"], w),
                  "pro": "\n".join(f"      <p>{markup(p, w + '.pro')}</p>" for p in tp["pro"]),
                  "kid": "\n".join(f"      <p>{markup(p, w + '.noob')}</p>" for p in tp["noob"]),
                  "diagram": "    " + svg_diagram(d["kind"], d["items"], w),
                  "caption": markup(d["caption"], w + ".diagram.caption"),
                  "used_in": used_html}
        out = re.sub(r"\{\{(\w+)\}\}", lambda m: values[m.group(1)] if m.group(1) in values else m.group(0), tpl)
        if (left := re.findall(r"\{\{\w+\}\}", out)):
            raise Refuse(f"topic template placeholders without a value: {sorted(set(left))}")
        pages[slug] = out
    return pages


def render(c: dict) -> tuple[str, list[str], list[str], dict[str, str]]:
    hidden: list[str] = []
    unlinked: list[str] = []
    by_slug, topic_lookup = load_topics()
    used_in: dict[str, list[str]] = {}
    ident = need(c, "identity", "content", dict)
    first, last = plain(need(ident, "first", "identity"), "identity.first"), plain(need(ident, "last", "identity"), "identity.last")
    handle, host = plain(need(ident, "handle", "identity"), "identity.handle"), plain(need(ident, "host", "identity"), "identity.host")
    if not re.fullmatch(r"[a-z0-9_-]+", ident["handle"]) or not re.fullmatch(r"[a-z0-9_-]+", ident["host"]):
        raise Refuse("identity.handle/host: lowercase letters, digits, - and _ only (they are shown as a shell prompt)")
    full = f"{first} {last}"
    user, domain = check_email(need(ident, "email", "identity"), "identity.email")
    photo = need(ident, "photo", "identity")
    keep_top = ident.get("photo_keep_top", 1.0)
    if not isinstance(keep_top, (int, float)) or not 0.2 <= keep_top <= 1.0:
        raise Refuse("identity.photo_keep_top: a number between 0.2 and 1.0")
    ensure_photo(photo, float(keep_top))
    design = need(c, "design", "content", dict)
    global MINIMAP
    MINIMAP = load_minimap(need(design, "minimap", "design"))
    pal = load_palette(need(design, "palette", "design"))
    global PALETTE
    PALETTE = pal

    meta = need(c, "meta", "content", dict)
    description = plain(need(meta, "description", "meta"), "meta.description")
    site_url = check_url(meta.get("url", ""), "meta.url")
    image = meta.get("image", "")
    if image and not (SRC / "assets" / image).is_file():
        raise Refuse(f"meta.image: src/assets/{image} does not exist")
    social = [
        f'<meta property="og:type" content="profile">',
        f'<meta property="og:title" content="{full} — {plain(need(ident, "role", "identity"), "identity.role")}">',
        f'<meta property="og:description" content="{description}">',
        '<meta name="twitter:card" content="summary">',
    ]
    if site_url:
        social += [f'<link rel="canonical" href="{site_url}">', f'<meta property="og:url" content="{site_url}">']
        if image:
            social.append(f'<meta property="og:image" content="{site_url.rstrip("/")}/assets/{image}">')
    json_ld = {
        "@context": "https://schema.org", "@type": "Person", "name": html.unescape(full),
        "givenName": ident["first"], "familyName": ident["last"], "email": f"mailto:{ident['email']}",
        "address": {"@type": "PostalAddress", "addressLocality": ident["location"]},
        "description": html.unescape(description),
    }
    if site_url:
        json_ld["url"] = site_url

    nav = need(c, "nav", "content", dict)
    nav_links = "\n".join(
        f'    <li><a href="#{k}">{plain(need(nav, k, "nav"), f"nav.{k}")}</a></li>'
        for k in ("about", "skills", "projects", "experience", "achievements", "certifications", "contact"))

    hero = need(c, "hero", "content", dict)
    typed = need(hero, "typed", "hero", list)
    for i, t in enumerate(typed):
        plain(t, f"hero.typed[{i}]")
    stats = need(hero, "stats", "hero", list)
    hero_stats = "\n".join(
        f'        <div><dt>{plain(need(s, "label", f"hero.stats[{i}]"), "label")}</dt>'
        f'<dd>{plain(need(s, "value", f"hero.stats[{i}]"), "value")}</dd></div>'
        for i, s in enumerate(stats))

    about = need(c, "about", "content", dict)
    paras = need(about, "paragraphs", "about", list)
    about_paragraphs = "\n".join(f"          <p>{markup(p, f'about.paragraphs[{i}]')}</p>" for i, p in enumerate(paras))
    term_html = []
    for i, t in enumerate(need(about, "terminal", "about", list)):
        w = f"about.terminal[{i}]"
        cmd = plain(need(t, "cmd", w), w)
        term_html.append(
            f'          <div class="cmd"><span class="ps-user">{handle}</span><span class="ps-sym">@</span>'
            f'<span class="ps-host">{host}</span><span class="ps-sym">:~$</span> {cmd}</div>')
        for j, line in enumerate(need(t, "out", w, list)):
            if isinstance(line, str) and line.startswith("//"):
                term_html.append(f'          <div class="out t-muted">{plain(line, w)}</div>')
            else:
                term_html.append(f'          <div class="out">{markup(line, f"{w}.out[{j}]")}</div>')
        term_html.append('          <div class="gap"></div>')
    terminal = "\n".join(term_html)

    skills = need(c, "skills", "content", dict)
    skills_html = "\n".join(
        f'      <div class="skill-box"><h3>{plain(need(g, "title", f"skills.groups[{i}]"), "title")}</h3>'
        f'{chips(need(g, "items", f"skills.groups[{i}]", list), f"skills.groups[{i}].items", topic_lookup if g.get("linked", True) else None, unlinked)}</div>'
        for i, g in enumerate(need(skills, "groups", "skills", list)))

    projects = need(c, "projects", "content", dict)
    proj_html = []
    for i, p in enumerate(need(projects, "featured", "projects", list)):
        w = f"projects.featured[{i}]"
        tone = need(p, "tone", w)
        if tone not in BADGE_TONES:
            raise Refuse(f"{w}.tone: must be one of {BADGE_TONES}, got {tone!r}")
        badges = []
        for dm in need(p, "domains", w, list):
            if (dslug := topic_lookup.get(dm.lower())):
                badges.append(f'<a class="proj-badge b-{tone}" href="topics/{dslug}.html" target="_blank" rel="noopener">{plain(dm, f"{w}.domains")}</a>')
                used_in.setdefault(dslug, [])
                if p["title"] not in used_in[dslug]:
                    used_in[dslug].append(p["title"])
            else:
                unlinked.append(dm)
                badges.append(f'<span class="proj-badge b-{tone}">{plain(dm, f"{w}.domains")}</span>')
        badges = "".join(badges)
        title_url = check_url(p.get("url", ""), f"{w}.url")
        if title_url:
            title_html = f'<a href="{html.escape(title_url)}" target="_blank" rel="noopener noreferrer">{plain(need(p, "title", w), w)}</a>'
        else:
            title_html = plain(need(p, "title", w), w)
            hidden.append(f"{p['title']} → title link (url)")
        for s_item in need(p, "stack", w, list):
            if (sl := topic_lookup.get(s_item.lower())):
                used_in.setdefault(sl, [])
                if p["title"] not in used_in[sl]:
                    used_in[sl].append(p["title"])
        links = []
        for label, url in need(p, "links", w, dict).items():
            url = check_url(url, f"{w}.links.{label}")
            if url:
                links.append(f'<a class="plink" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">{link_icon(label)}{plain(label, w)}</a>')
            else:
                hidden.append(f"{p['title']} → {label}")
        links_html = f'\n         <div class="proj-links">{"".join(links)}</div>' if links else ""
        note = p.get("note", "")
        note_html = f'\n         <p class="proj-note">{plain(note, f"{w}.note")}</p>' if note else ""
        proj_html.append(
            f'      <article class="proj" data-idx="{i + 1:02d}">\n'
            f'         <div class="proj-badges">{badges}</div>\n'
            f'         <h3>{title_html}</h3>{note_html}\n'
            f'         <p>{markup(need(p, "desc", w), w)}</p>\n'
            f'         {chips(need(p, "stack", w, list), f"{w}.stack", topic_lookup, unlinked)}{links_html}\n'
            f'      </article>')
    projects_html = "\n".join(proj_html)
    archive_html = "\n".join(
        f'        <div class="mini"><h4>{plain(need(a, "title", f"projects.archive[{i}]"), "title")}</h4>'
        f'<p>{markup(need(a, "desc", f"projects.archive[{i}]"), "desc")}</p></div>'
        for i, a in enumerate(need(projects, "archive", "projects", list)))

    exp = need(c, "experience", "content", dict)
    experience_html = "\n".join(
        f'      <li class="t-item"><p class="t-date">{plain(need(e, "date", f"experience.entries[{i}]"), "date")}</p>'
        f'<h3>{plain(need(e, "role", f"experience.entries[{i}]"), "role")}</h3>'
        f'<h4>{plain(need(e, "org", f"experience.entries[{i}]"), "org")}</h4>'
        f'<p>{markup(need(e, "desc", f"experience.entries[{i}]"), "desc")}</p></li>'
        for i, e in enumerate(need(exp, "entries", "experience", list)))

    ach = need(c, "achievements", "content", dict)
    achievements_html = "\n".join(
        f'      <div class="ach"><p class="big">{icon(need(a, "icon", f"achievements.items[{i}]"), "ach-figure")}'
        f'{plain(need(a, "big", f"achievements.items[{i}]"), "big")}</p>'
        f'<h3>{plain(need(a, "title", f"achievements.items[{i}]"), "title")}</h3>'
        f'<p>{markup(need(a, "desc", f"achievements.items[{i}]"), "desc")}</p></div>'
        for i, a in enumerate(need(ach, "items", "achievements", list)))

    certs = need(c, "certifications", "content", dict)
    cert_html = []
    for i, ce in enumerate(need(certs, "items", "certifications", list)):
        w = f"certifications.items[{i}]"
        cu = check_url(ce.get("url", ""), f"{w}.url")
        title = plain(need(ce, "title", w), w)
        if cu:
            title = f'<a href="{html.escape(cu)}" target="_blank" rel="noopener noreferrer">{title}</a>'
        else:
            hidden.append(f"certification: {ce['title']} → url")
        cert_html.append(f'      <li class="cert"><span class="cert-title">{title}</span><span class="cert-issuer">{plain(need(ce, "issuer", w), w)}</span></li>')
    certifications_html = "\n".join(cert_html)

    contact = need(c, "contact", "content", dict)
    contact_links = []
    resume = contact.get("resume", "")
    if resume:
        if not re.fullmatch(r"[A-Za-z0-9._-]+\.pdf", resume) or not (SRC / "assets" / resume).is_file():
            raise Refuse(f"contact.resume: src/assets/{resume} must exist and be a .pdf")
        contact_links.append(f'        <a class="btn" href="assets/{html.escape(resume)}" download>{icon("pen")}{plain(need(contact, "resume_label", "contact"), "contact.resume_label")}</a>')
    for label, url in need(contact, "links", "contact", dict).items():
        url = check_url(url, f"contact.links.{label}")
        if url:
            contact_links.append(f'        <a class="btn" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">{link_icon(label)}{plain(label, "contact.links")}</a>')
        else:
            hidden.append(f"contact → {label}")

    footer = need(c, "footer", "content", dict)
    year = str(dt.date.today().year)
    footer_html = markup(need(footer, "line", "footer").replace("{year}", year), "footer.line")

    def title_md(s: str, w: str) -> str:
        return markup(s, w)

    def title_plain(s: str) -> str:
        return html.escape(s.replace("**", ""), quote=True)

    minimap = need(c, "minimap", "content", dict)
    map_text = {key: plain(need(minimap, key, "minimap"), f"minimap.{key}")
                for key in ("title", "toggle", "start", "hint", "scrub")}
    # optional labels — a module may use them or not (the spider stencils `tag` on its abdomen)
    for key in ("tag",):
        map_text[key] = plain(str(minimap.get(key, "")), f"minimap.{key}")
    # ...and the tone it is drawn in, published to the module as --map-tag
    tag_tone = str(minimap.get("tag_tone", "secondary"))
    if tag_tone not in TONES:
        raise Refuse(f"minimap.tag_tone: must be one of {TONES}, got {tag_tone!r}")
    global MAP_VARS
    MAP_VARS = (f"/* generated by render.py from [minimap] tag_tone = {tag_tone!r} */\n"
                f":root{{--map-tag:var(--{tag_tone});--map-tag-rgb:var(--{tag_tone}-rgb)}}\n")
    map_stops = [("top", map_text["start"])] + [
        (k, plain(nav[k], f"nav.{k}")) for k in
        ("about", "skills", "projects", "experience", "achievements", "certifications", "contact")]
    rail_stops = "\n".join(
        f'        <li><a href="#{key}" aria-label="{label}" data-label="{label}">'
        f'<span class="map-node" aria-hidden="true"></span>'
        f'<span class="map-index" aria-hidden="true">{i:02d}</span>'
        f'<span class="map-tooltip" aria-hidden="true">{i:02d} / {label}</span></a></li>'
        for i, (key, label) in enumerate(map_stops))

    # the 404 ghost is optional: with no [design] ghost_text there is no element
    ghost_word = plain(str(design.get("ghost_text", "")), "design.ghost_text")
    ghost_html = (f'<div class="fx-ghost" id="ghost" aria-hidden="true" data-text="{ghost_word}">{ghost_word}</div>'
                  if ghost_word.strip() else "")

    values = {
        "csp": html.escape(META_CSP, quote=True),
        **{f"map_{key}": value for key, value in map_text.items()},
        "title": f"{full} — {plain(ident['role'], 'identity.role')}",
        "description": description,
        "full_name": full,
        "meta_social": "\n".join(social),
        "json_ld": '<script type="application/ld+json">' + json.dumps(json_ld, ensure_ascii=False) + "</script>",
        "handle": handle, "host": host,
        "rain_hex": need(design, "rain_text", "design").encode("utf-8").hex().upper(),
        "ghost": ghost_html,
        "status": plain(need(ident, "status", "identity"), "identity.status"),
        "nav_links": nav_links,
        "photo": html.escape(photo),
        "hero_kicker": plain(need(hero, "kicker", "hero"), "hero.kicker"),
        "first_upper": first.upper(), "last_upper": last.upper(),
        "hero_lead": markup(need(hero, "lead", "hero"), "hero.lead"),
        "typed_json": html.escape(json.dumps(typed, ensure_ascii=False), quote=True),
        "typed_first": html.escape(typed[0]),
        "cta_primary": plain(need(hero, "cta_primary", "hero"), "hero.cta_primary"),
        "cta_secondary": plain(need(hero, "cta_secondary", "hero"), "hero.cta_secondary"),
        "scroll_hint": plain(need(hero, "scroll_hint", "hero"), "hero.scroll_hint"),
        "hero_stats": hero_stats,
        "about_tag": plain(need(about, "tag", "about"), "about.tag"),
        "about_title": title_md(need(about, "title", "about"), "about.title"),
        "about_title_plain": title_plain(about["title"]),
        "terminal": terminal,
        "about_paragraphs": about_paragraphs,
        "skills_tag": plain(need(skills, "tag", "skills"), "skills.tag"),
        "skills_title": title_md(need(skills, "title", "skills"), "skills.title"),
        "skills_title_plain": title_plain(skills["title"]),
        "skills": skills_html,
        "projects_tag": plain(need(projects, "tag", "projects"), "projects.tag"),
        "projects_title": title_md(need(projects, "title", "projects"), "projects.title"),
        "projects_title_plain": title_plain(projects["title"]),
        "projects": projects_html,
        "archive_label": plain(need(projects, "archive_label", "projects"), "projects.archive_label"),
        "archive": archive_html,
        "experience_tag": plain(need(exp, "tag", "experience"), "experience.tag"),
        "experience_title": title_md(need(exp, "title", "experience"), "experience.title"),
        "experience_title_plain": title_plain(exp["title"]),
        "experience": experience_html,
        "achievements_tag": plain(need(ach, "tag", "achievements"), "achievements.tag"),
        "achievements_title": title_md(need(ach, "title", "achievements"), "achievements.title"),
        "achievements_title_plain": title_plain(ach["title"]),
        "achievements": achievements_html,
        "certifications_tag": plain(need(certs, "tag", "certifications"), "certifications.tag"),
        "certifications_title": title_md(need(certs, "title", "certifications"), "certifications.title"),
        "certifications_title_plain": title_plain(certs["title"]),
        "certifications": certifications_html,
        "contact_tag": plain(need(contact, "tag", "contact"), "contact.tag"),
        "contact_title": title_md(need(contact, "title", "contact"), "contact.title"),
        "contact_title_plain": title_plain(contact["title"]),
        "contact_blurb": markup(need(contact, "blurb", "contact"), "contact.blurb"),
        "email_label": plain(need(contact, "email_label", "contact"), "contact.email_label"),
        "email_icon": icon("envelope"),
        "email_user_rev": html.escape(user[::-1]), "email_domain_rev": html.escape(domain[::-1]),
        "email_noscript": html.escape(f"{user} [at] {domain.replace('.', ' [dot] ')}"),
        "contact_links": "\n".join(contact_links),
        "footer": footer_html,
        "rail_stops": rail_stops,
        "theme_bg": pal["bg"],
    }
    tpl = (SRC / "index.html").read_text(encoding="utf-8").replace("{{minimap}}", MINIMAP["template.html"])
    out = re.sub(r"\{\{(\w+)\}\}", lambda m: values[m.group(1)] if m.group(1) in values else m.group(0), tpl)
    leftover = re.findall(r"\{\{\w+\}\}", out)
    if leftover:
        raise Refuse(f"template placeholders without a value: {sorted(set(leftover))}")
    global PHOTO_CSS
    pw, ph = webp_size(SRC / "assets" / photo)
    # the silhouette is a variable so style.css can intersect it with the edge fades
    PHOTO_CSS = f".hero-photo{{--photo-ratio:{pw}/{ph};--photo-url:url(assets/{photo})}}\n"
    topics_cfg = need(c, "topics", "content", dict)
    common = {"full_name": full, "handle": handle, "host": host, "footer": footer_html, "theme_bg": pal["bg"],
              "pro_label": plain(need(topics_cfg, "pro_label", "topics"), "topics.pro_label"),
              "noob_label": plain(need(topics_cfg, "noob_label", "topics"), "topics.noob_label")}
    topic_pages = render_topics(by_slug, used_in, common)
    return out, hidden, sorted(set(unlinked), key=str.lower), topic_pages


# ── output ──────────────────────────────────────────────────────────────────
PHOTO_CSS = ""
PALETTE: dict = {}
MINIMAP: dict = {}
MAP_VARS = ""


def write_dist(index_html: str, topic_pages: dict[str, str]) -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    (DIST / "index.html").write_text(index_html, encoding="utf-8")
    (DIST / "photo.css").write_text("/* generated by render.py: the photo file name comes from content */\n" + PHOTO_CSS)
    (DIST / "palette.css").write_text(palette_css(PALETTE))
    (DIST / "minimap.css").write_text(MAP_VARS + MINIMAP["style.css"])
    (DIST / "minimap.js").write_text(MINIMAP["behavior.js"])
    (DIST / "topics").mkdir()
    for slug, page in topic_pages.items():
        (DIST / "topics" / f"{slug}.html").write_text(page, encoding="utf-8")
    for name in ("style.css", "app.js"):
        shutil.copy2(SRC / name, DIST / name)
    shutil.copytree(SRC / "assets", DIST / "assets", ignore=shutil.ignore_patterns("*.src-sha256", ".DS_Store"))
    (DIST / "assets" / "favicon.svg").write_text(favicon_svg(PALETTE))
    # one header set, in the two formats static hosts read
    (DIST / "vercel.json").write_text(json.dumps({
        "$schema": "https://openapi.vercel.sh/vercel.json",
        "cleanUrls": False, "trailingSlash": False,
        "headers": [{"source": "/(.*)", "headers": [{"key": k, "value": v} for k, v in HEADERS]}],
    }, indent=2) + "\n")
    (DIST / "_headers").write_text("/*\n" + "".join(f"  {k}: {v}\n" for k, v in HEADERS))
    (DIST / "robots.txt").write_text("User-agent: *\nAllow: /\n")


def gate_dist() -> None:
    text_files = [p for p in DIST.rglob("*") if p.is_file() and p.suffix in TEXT_SUFFIXES]
    for p in text_files + [CONTENT, SRC / "index.html", SRC / "style.css", SRC / "app.js"]:
        t = p.read_text(encoding="utf-8")
        rel = p.relative_to(ROOT)
        if (hit := scan_secrets(t)):
            raise Refuse(f"{rel}: contains a secret-shaped string ({hit})")
        if scan_name(t):
            raise Refuse(f"{rel}: contains the standalone name; use the full first name")
        if p.suffix in {".html", ".css", ".js"} and scan_external(t):
            raise Refuse(f"{rel}: references a resource on another origin; the site must be self-contained")
    print("gate: secrets         ok (%d text files)" % (len(text_files) + 4))
    print("gate: name            ok")
    print("gate: self-contained  ok")

    pages = sorted(DIST.rglob("*.html"))
    css = "\n".join((DIST / name).read_text(encoding="utf-8") for name in ("style.css", "photo.css", "minimap.css"))
    src_css = (SRC / "style.css").read_text(encoding="utf-8") + MINIMAP["style.css"]
    if (lit := re.findall(r"#[0-9a-fA-F]{6}\b|rgba?\((?!var\()\d+,\s*\d+,\s*\d+(?!,\s*\d+\))", src_css)):
        lit = [x for x in lit if x.lower() not in ("#000000", "#ffffff", "rgba(0,0,0", "rgba(255,255,255")]   # neutral shadows/tints are not palette
        if lit:
            raise Refuse(f"stylesheet: colour literals found — use palette variables instead: {sorted(set(lit))[:8]}")
    refs: set[Path] = set()
    for page in pages:
        text = page.read_text(encoding="utf-8")
        for r in re.findall(r"(?:src|href)=\"(?!#|mailto:|https?:)([^\"#]+)(?:#[^\"]*)?\"", text):
            refs.add((page.parent / r).resolve())
        csp_meta = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', text)
        if not csp_meta or html.unescape(csp_meta.group(1)) != META_CSP:
            raise Refuse(f"{page.relative_to(DIST)}: CSP meta tag differs from the shared security policy")
        if re.search(r"<script(?![^>]*\bsrc=)(?![^>]*application/ld\+json)", text) or re.search(r"\son\w+=", text):
            raise Refuse(f"{page.relative_to(DIST)}: inline script or event handler found; the CSP would block it")
    refs |= {(DIST / m.strip("'\"")).resolve() for m in re.findall(r"url\(([^)]+)\)", css) if not m.startswith(("data:", "\"data:", "'data:"))}
    refs |= {(DIST / "assets/fonts" / m).resolve() for m in re.findall(r"url\(([^)]+\.woff2)\)", (DIST / "assets/fonts/fonts.css").read_text())}
    missing = [str(r.relative_to(DIST)) for r in refs if not r.is_file()]
    if missing:
        raise Refuse(f"referenced files missing from dist: {sorted(set(missing))}")
    print("gate: local assets    ok (%d referenced files present, %d pages)" % (len(refs), len(pages)))
    print("gate: CSP             ok (meta on every page, no inline script)")
    # Every file copied from src/ must be byte-identical in dist/. The cloud folder has
    # handed back an empty copy before (F21): a 0-byte style.css shipped as a blank page.
    for rel in ("style.css", "app.js", *[f"assets/{p.relative_to(SRC / 'assets')}" for p in (SRC / "assets").rglob("*") if p.is_file() and not p.name.endswith(".src-sha256") and p.name != ".DS_Store" and p.name != "favicon.svg"]):
        a, b = SRC / rel, DIST / rel
        if not b.is_file() or hashlib.sha256(a.read_bytes()).digest() != hashlib.sha256(b.read_bytes()).digest():
            raise Refuse(f"{rel}: dist copy differs from src (size {b.stat().st_size if b.is_file() else 'missing'} vs {a.stat().st_size}) — the folder returned a bad copy; rebuild")
    for name in ("palette.css", "photo.css", "minimap.css", "minimap.js"):
        if (DIST / name).is_file() and (DIST / name).stat().st_size == 0:
            raise Refuse(f"{name}: generated file is empty")
    print("gate: copies intact   ok (dist files hash-identical to src)")
    # Every shipped script must at least parse. This catches a bad edit, not a
    # runtime error: F18 shipped a ReferenceError that only a browser would show.
    node = shutil.which("node")
    scripts = sorted(DIST.glob("*.js"))
    if node:
        for js in scripts:
            res = subprocess.run([node, "--check", str(js)], capture_output=True, text=True)
            if res.returncode != 0:
                raise Refuse(f"{js.relative_to(DIST)} does not parse:\n{res.stderr.strip()}")
        print("gate: script syntax   ok (%d files parse under node --check)" % len(scripts))
    else:
        print("gate: script syntax   SKIPPED — node not installed (RULES 2.6: a decision not to test, recorded here)")


def dist_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(DIST.rglob("*")):
        if p.is_file() and p.name != ".build.json":
            h.update(str(p.relative_to(DIST)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def public_files() -> dict[str, str]:
    """Every published page/asset, excluding build and host configuration."""
    return {p.relative_to(DIST).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(DIST.rglob('*')) if p.is_file()
            and p.name not in {'.build.json', 'vercel.json', '_headers'}}


def main() -> None:
    if sys.version_info < (3, 11):
        raise Refuse("Python 3.11 or newer is required (tomllib)")
    fire_test_gates()
    try:
        content = tomllib.loads(CONTENT.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise Refuse(f"content/site.toml does not parse: {e}")
    index_html, hidden, unlinked, topic_pages = render(content)
    if unlinked:
        raise Refuse(f"{len(unlinked)} chip(s)/badge(s) have no explainer in content/topics/ — write one (see content/topics/_README.md) or mark the group linked = false: {', '.join(unlinked)}")
    write_dist(index_html, topic_pages)
    gate_dist()
    digest = dist_hash()
    (DIST / ".build.json").write_text(json.dumps({
        "sha256": digest, "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "index_sha256": hashlib.sha256((DIST / "index.html").read_bytes()).hexdigest(),
        "files": public_files(),
    }, indent=2) + "\n")
    size = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())
    print(f"render: dist/ written, {size // 1024} KB, {len(topic_pages)} topic pages, palette '{PALETTE.get('name', '?')}', sha256 {digest[:16]}…")
    if hidden:
        print(f"note: {len(hidden)} link(s) have no url yet and are hidden from visitors:")
        for h in hidden:
            print(f"      · {h}")


if __name__ == "__main__":
    main()
