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

A refused build prints `render: REFUSED — <reason>`, exits non-zero, and leaves
the previous `dist/` exactly as it was. The site is rendered into
`dist.candidate/`, every gate runs there, and only a candidate that passed them
all replaces `dist/`; the old `dist/` is kept as `dist.old/` until that swap
succeeds. A refused or failed candidate is deleted.

Every run starts by fire-testing the gates below: each one is fed synthetic bad
inputs it must refuse and a clean input it must pass, and a gate that fails its
own test refuses the build. The fake credentials in those fixtures are joined
together at run time, so none appears whole in `render.py`.

- **A missing or wrong-typed field in `content/site.toml`.** Every field the
  page uses is checked for presence and type (text, list, table, number,
  true/false), and the refusal names the field, such as
  `identity.location: must be non-empty text, got 5`. A `KeyError`,
  `TypeError`, `AttributeError`, `ValueError` or `IndexError` raised while
  rendering the content is also turned into a `REFUSED` message instead of a
  traceback; that fallback is not fire-tested.
- **A link in `content/site.toml` that is not `https://`** (the page URL,
  project, certification and contact links). A link may be `""`, which hides it.
- **A credential-shaped string:** a private-key block, an AWS access key, an
  `sk-`/`sk-ant-` key, a `gh[pousr]_` or `github_pat_` GitHub token, a Slack
  `xox[abprs]-` token, a Google `AIza…` key, a JWT, a password/secret/token/API
  key assignment, or a run of 40 or more lower-case or upper-case hex digits.
  Scanned: every `.html .css .js .json .svg .txt .toml .md` file in the output,
  plus `content/site.toml`, `src/index.html`, `src/style.css` and `src/app.js`.
  Binary files, such as the résumé PDF and images, are not scanned (the résumé
  has its own check, below).
- **Anything that would make the browser contact another site**, in the
  output's `.html`, `.css`, `.js` and `.svg` files: a `src`/`href` (including
  `xlink:href`) on `script`, `link`, `img`, `image`, `source`, `iframe`,
  `video`, `audio`, `object` or `embed` that starts `http://`, `https://` or
  `//`; such an address in any `srcset` entry or a `poster`; CSS `url()` or
  `@import` of one; a static or dynamic `import` of one. `fetch(`,
  `new XMLHttpRequest`, `new WebSocket`, `new EventSource` and
  `navigator.sendBeacon` are refused whatever their address. Ordinary `<a href>`
  links and the page's canonical link are allowed.
- **A colour written directly in a stylesheet**, in the declaration values of
  `src/style.css` and the selected minimap's `style.css`: `#rgb`, `#rgba`,
  `#rrggbb`, `#rrggbbaa`, `rgb()`/`rgba()` with number channels (comma- or
  space-separated), and `hsl()`/`hsla()`. Allowed: `#000`, `#fff`, `#000000`,
  `#ffffff`, the print stylesheet's greys `#ccc` and `#222`, and black or white
  `rgb()`/`rgba()` at any opacity. Selectors (an id such as `#fab`), comments
  and `url()` are not read as colours.
- **A skill with no explainer.** Every item of a skills group, every project
  stack item and every project domain badge needs a file in `content/topics/`
  whose name or alias matches it (ignoring case); a skills group with
  `linked = false` is exempt.
- **Two explainers claiming the same skill:** a name or alias, ignoring case,
  claimed by two files in `content/topics/`.
- **A missing local file:** every `src`/`href` (double- or single-quoted) and
  every `srcset` entry on every output page, every `url()` in `style.css`,
  `photo.css` and `minimap.css`, and every `.woff2` font in `fonts.css` must
  name a file that exists in the output.
- **The owner's first name shortened on its own**, anywhere the credential scan
  looks.

These also refuse the build, but are not fire-tested: Python older than 3.11;
`content/site.toml`, a palette or a topic file that does not parse; a palette
colour that is not `#rrggbb`; a topic file with a missing field or a name that
is not lowercase letters, digits and hyphens; a minimap folder missing a file,
or with a file that is empty or fails the credential, name or other-site
checks; a missing photo, résumé or preview image, or a photo that is not WebP
or PNG; markup that is
unbalanced or used where it is not allowed; an invalid e-mail address, handle,
host, tone, icon, photo crop or topic diagram; a template placeholder left
unfilled; a page whose Content Security Policy meta tag differs from the
shared policy, or that has an inline script or event handler; a file copied
from `src/` that differs from its source; an empty generated file; and a
script that fails `node --check` (skipped, with a notice, when Node.js is not
installed).

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
