# Minimap modules

On the **laptop**, select a module independently from the palette in
`content/site.toml`, then run `bash scripts/build.sh`:

```toml
[design]
palette = "neon-noir"
minimap = "spider"
```

| Module | Design |
|---|---|
| `spider` | **Current selection.** A dotted silk thread with a diamond per section; a spider hangs abdomen-up at the end of the silk it has spun and descends as the reader scrolls, legs scurrying while the page moves, glitching every five seconds. Left alone it settles, grooms, eats, tests its thread, dozes, and after thirteen minutes climbs home to the top and sleeps until the reader returns; its front two pairs alternate fixed grips on the silk as the body rises, while the rear two pairs stay folded beside the abdomen without stepping. Direction changes use a smooth body rotation; small scroll reversals are filtered. Gait follows rendered distance, the silk and body share one frame loop, delayed frames are bounded, and the loop sleeps when settled or hidden. Every mood is movement only — no labels, no tooltip. Hidden below 1180 px. The design first published on 21 September 2026. |
| `nocturne` | Cocoon transforms into a moth along a living vine; leaf stops, pointer response, mouse/touch dragging. Saved, not selected. |
| `rift` | Saved side seam, fractured shard, pointer attraction and drag navigation. |
| `orbit` | Saved compact button that opens an orbital dial. |

Each module is a folder with exactly these required files:

- `template.html`: the navigation markup, using the content placeholders below.
- `style.css`: scoped styles using palette variables; no hardcoded colours.
- `behavior.js`: self-contained JavaScript, no dependencies or external resources.

The renderer discovers a module by folder name. No registration table or main
page edits are required. It inserts the template and emits the selected styles
and behaviour as `dist/minimap.css` and `dist/minimap.js`; inactive modules are
not shipped. Missing files, unsafe names and source safety failures refuse the
build. New designs get new folders so saved designs remain available.

Templates can use `{{map_title}}`, `{{map_toggle}}`, `{{map_start}}`,
`{{map_hint}}`, `{{map_scrub}}`, the optional `{{map_tag}}` (empty when the
content file omits it) and must contain `{{rail_stops}}`. A module that draws
`{{map_tag}}` should paint it with `var(--map-tag)` / `rgba(var(--map-tag-rgb),…)`,
which the build writes into `dist/minimap.css` from `[minimap] tag_tone` — a
palette slot name, refused if it is not one.
The labels live in `[minimap]` and `[nav]` in `content/site.toml`.
Generated stops contain a real anchor, `aria-label`, `data-label` and three
optional presentation spans: `.map-node`, `.map-index`, `.map-tooltip`.
Hide the spans the design does not use. Keep navigation usable by keyboard;
respect reduced motion and hide script-dependent UI without JavaScript.

Nocturne's paths interpolate from a closed cocoon to open moth wings as the
page progresses. Hovering or focusing the familiar opens it further. Teal wing
veins, gold markings and a faint rotating seal draw on dark magical anime
references; the design is original SVG, not an image dependency. Reduced motion
snaps to the corresponding shape. Its slim mobile rail reserves its own space;
viewports at most 620 pixels high use the existing top navigation. All earlier
module files are preserved unchanged.

Rift measures untransformed section positions, then maps each interval to a
segment of the side seam. Its spring responds to scrolling and horizontal
pointer attraction. Dragging reverses that mapping. The satellites separate
with velocity and pointer attraction; animation frames stop when settled.
Short viewports below 581 pixels high use the existing top navigation. Pointer
drag, touch drag, section links and the slider's arrow/Home/End keys are
available in taller viewports. Arrow Up/Right increase the slider value;
Arrow Down/Left decrease it. Page Up/Down scroll by ten percent.

On the **laptop**, verify every saved palette/module combination with:

```bash
python3 scripts/check-design.py
```

This builds and gates each combination in a temporary folder without changing
`site.toml`, the saved palettes, or `dist/`. Browser interactions need a local
preview; the local verification record is in `Planning/portfolio-rev1.md` §5.

The spider's browser regression check runs on the **laptop** against a built
local preview:

```bash
node scripts/check-spider.cjs http://127.0.0.1:8791/
```

It uses Puppeteer 23.11.1 with Chrome 131 headless shell as test tooling only;
see the script header for `PUPPETEER_MODULE` and `BROWSER_EXECUTABLE` when reusing
an existing installation. It checks real rendered leg contacts, body rotation,
scroll jitter, reversals, reduced motion, offline scrolling, CPU throttling,
an interrupted frame, resize, idle home/wake, and click-to-top. Disposable
screenshots and measurements go to `build/spider-check/`; they are not deployed.
