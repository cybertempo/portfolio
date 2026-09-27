# sreenandan-pradeep — portfolio site

The source of **https://sreenandan-pradeep.vercel.app**: a one-page portfolio
with a short explainer page for each skill, built from a single content file
into plain static files.

No framework and no build dependencies beyond **Python 3.11+** (standard library
only). No trackers, no cookies, no third-party requests: fonts, scripts and
images are all served from the site itself.

## Build it

```bash
bash scripts/build.sh           # renders content/ + src/ into dist/
bash scripts/build.sh --serve   # the same, then a local preview
```

`dist/` is generated output: deleted and rewritten by every build, never edited.

## How it is put together

| Path | What it is |
|---|---|
| `content/site.toml` | every string on the page: identity, projects, experience, contact |
| `content/topics/*.toml` | one file per skill; each becomes an explainer page with a small diagram |
| `content/palettes/*.toml` | the colour scheme; the only place a colour is written |
| `src/` | the page template, stylesheet, script, self-hosted fonts and assets |
| `scripts/render.py` | the build: validates the content, then writes `dist/` |
| `scripts/verify-live.sh` | checks the deployed site against the build |
| `scripts/deploy.sh` | builds, publishes to Vercel, then runs the live check |

## What the build refuses

The build produces nothing at all if any of these is true, and every check is
tested against a deliberately bad input on each run before it is trusted:

- a field is missing or malformed, or a link uses `http://`
- the output contains anything shaped like a credential (key blocks, API keys,
  tokens, long hex strings)
- the page would load a script, style, font or image from another site
- the stylesheet contains a colour written directly, instead of one from the palette
- a skill on the page has no explainer, or two explainers claim the same skill
- an asset the page refers to does not exist

## What a visitor is protected from

- A strict Content Security Policy and security headers, written once in
  `render.py` and emitted for every format a host reads (`vercel.json`,
  `_headers`, and the page's own meta tag).
- No analytics, no cookies, no requests to anyone but this site.
- The e-mail address is not in the HTML: it is assembled by script on load
  (and shown spelled out to visitors without JavaScript).

## The résumé

`src/assets/sreenandan-pradeep-resume.pdf` is built from a LaTeX source kept
out of this repository, by `scripts/build-resume.sh`. That script compiles the
PDF fresh, then `scripts/check-pdf-private.py` refuses to publish it if a phone
number appears anywhere — in the page text, the document metadata, or any
string inside the file, where link targets hide. E-mail is the only contact
method, by design.

## Publishing, and proving it

```bash
bash scripts/deploy.sh          # needs the Vercel CLI, signed in
bash scripts/verify-live.sh     # the live page must equal the build
```

`verify-live.sh` requires the live page's hash to equal the build's, the
security headers to be served, and — as a positive control — a made-up path to
*not* answer 200, so a catch-all or captive portal cannot pass the other checks.

## How it was built

Claude Code assisted with implementation and review. I directed the project and reviewed the final result.

## Licence

The code and content are © Sreenandan Pradeep, all rights reserved: you are
welcome to read them, but not to reuse them. The fonts in `src/assets/fonts/`
are © their authors under the SIL Open Font License 1.1; each licence is beside
its font.
