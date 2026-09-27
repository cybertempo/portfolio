# Palettes

One file per colour scheme. Pick one in `content/site.toml`:

```toml
[design]
palette = "nocturne"        # → content/palettes/nocturne.toml
```

Then on the **laptop** run `bash scripts/build.sh`. This is the only switch;
components, explainer pages, the selected minimap, favicon and browser theme follow it.

| Saved palette | Character |
|---|---|
| `nocturne` | True black, distinct midnight-grey panels, electric teal, antique-gold details (current local selection) |
| `midnight-teal` | Black, midnight grey, electric teal, cobalt/crimson glitch accents |
| `carbon-patina` | Charcoal, warm white, patina teal, amber highlights |
| `neon-noir` | Original neon cyan, purple, green and yellow |
| `arctic` | Cold slate, ice blue and mint |
| `ember` | Warm charcoal, amber and rust |

**Preserve saved palettes.** Add a new named TOML file for each new colour
direction; do not delete or overwrite an existing palette to try another.
A new file with the same keys is immediately selectable; no CSS or JavaScript
changes are needed. All previously saved palettes are unchanged.

The build turns the chosen file into `dist/palette.css` (CSS variables), draws
the favicon in its colours, and sets the browser theme colour. Nothing else
carries a colour: `style.css` only ever refers to the variables below, and the
build refuses a palette with a missing key or a value that is not `#rrggbb`.

| Key | Used for |
|---|---|
| `bg`, `bg2` | page background; nav bar / terminal title bar |
| `panel`, `panel2` | cards; the darker end of card gradients |
| `text`, `muted`, `faint` | body text; secondary text; hairlines and idle dots |
| `stroke` | the dark outline behind titles |
| `primary` | THE accent: second line of the name, heading words, buttons, minimap |
| `secondary` | lines, glows, badges of the second tone, the hostname |
| `tertiary` | scan line and small third-colour touches |
| `success` | terminal prompt, status pill, kicker |
| `warning` | achievements, certifications |
| `danger` | security badges, glitch layer, rain highlights |

Content tone names map to these slots: `primary secondary tertiary success
warning danger muted` — so `tone = "danger"` stays a warning colour whatever the
palette. To try a scheme, copy a file, change the values, change one line in
`site.toml`, build.
