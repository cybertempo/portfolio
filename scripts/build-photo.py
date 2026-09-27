#!/usr/bin/env python3
"""Derive the web photo from a background-removed PNG.  [LAPTOP]

    python3 scripts/build-photo.py source/<name>.png [keep-top]

keep-top: fraction of the cut-out's height to keep, measured from the top —
1.0 keeps the whole figure, 0.45 keeps head-to-chest. Comes from
[identity] photo_keep_top in content/site.toml; the build passes it.

Input : a PNG with a transparent background (the person on nothing).
Output: src/assets/<name>.webp — trimmed to the person plus a little air,
        1200 px wide, WebP with alpha — and src/assets/<name>.webp.src-sha256,
        the hash of the input, so the build knows when to run this again.

Normally you do not run this by hand: scripts/build.sh runs it whenever the
PNG in source/ has changed since the last build.

To swap the picture:
  1. Remove the background from the new photo. On a Mac: select the file in
     Finder → right-click → Quick Actions → Remove Background (built in since
     macOS 13; writes "<file> Background Removed.png" beside it). On Linux:
     `pip install rembg` then `rembg i in.jpg out.png`. Either way you get a
     PNG with transparency — this script refuses a photo that has none,
     because a rectangle of wall would be drawn onto the page.
  2. Save it as source/<name>.png.
  3. In content/site.toml set   photo = "<name>.webp"   under [identity].
  4. bash scripts/build.sh

Requires Pillow (python3 -m pip install pillow). Pillow is needed only for
this step; the rest of the build is standard library.
"""
import hashlib
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("build-photo: Pillow is not installed. On the LAPTOP: python3 -m pip install pillow")

ROOT = Path(__file__).resolve().parents[1]
WIDTH = 1200     # the hero never shows it wider than ~600 CSS px; 2× for retina
QUALITY = 82     # visually lossless at that size, about 1/15 the PNG


def main(src: Path, keep_top: float = 1.0) -> None:
    if not 0.2 <= keep_top <= 1.0:
        sys.exit("build-photo: keep-top must be between 0.2 and 1.0")
    if src.suffix.lower() != ".png":
        sys.exit(f"build-photo: {src.name}: expected a .png with transparency (see the header of this script)")
    im = Image.open(src)
    if im.mode not in ("RGBA", "LA") and "transparency" not in im.info:
        sys.exit(f"build-photo: {src.name} has no transparency — remove the background first (see the header of this script)")
    im = im.convert("RGBA")
    alpha = im.getchannel("A")
    bbox = alpha.point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox is None:
        sys.exit(f"build-photo: {src.name} is fully transparent")
    if (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) > 0.97 * im.width * im.height:
        sys.exit(f"build-photo: {src.name}: the opaque area is the whole frame — the background was not removed")
    pad = int(im.width * 0.02)
    im = im.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                  min(im.width, bbox[2] + pad), min(im.height, bbox[3] + pad)))
    if keep_top < 1.0:
        im = im.crop((0, 0, im.width, round(im.height * keep_top)))
        # re-trim horizontally: the kept part may be narrower than the whole figure
        bb = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        im = im.crop((max(0, bb[0] - pad), 0, min(im.width, bb[2] + pad), im.height))
    if im.width > WIDTH:
        im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)

    dest = ROOT / "src" / "assets" / (src.stem + ".webp")
    im.save(dest, "WEBP", quality=QUALITY, method=6)
    (dest.with_name(dest.name + ".src-sha256")).write_text(hashlib.sha256(src.read_bytes() + f"keep-top={keep_top}".encode()).hexdigest() + "\n")
    print(f"build-photo: {src.relative_to(ROOT)} → {dest.relative_to(ROOT)} "
          f"{im.width}x{im.height} ({dest.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    main(Path(sys.argv[1]).resolve(), float(sys.argv[2]) if len(sys.argv) == 3 else 1.0)
