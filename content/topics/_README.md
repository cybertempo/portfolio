# Topic explainers

One file per thing a visitor can click on (a skill chip, a stack item). The file
name is the page's URL slug: `docker.toml` → `topics/docker.html`.

```toml
name    = "Docker"                 # exact chip text; also matched via aliases
aliases = ["Docker Engine"]        # other chip texts that mean the same thing
tagline = "one sentence"
pro     = ["paragraph", "…"]       # the Pro tab: for practitioners   (**bold** allowed)
noob    = ["paragraph", "…"]       # the Noob tab: for someone new to all of it
[diagram]
kind    = "flow"                   # flow: boxes left→right with arrows
                                   # stack: layers top→bottom
                                   # hub: first item in the centre, the rest around it
items   = ["A", "B", "C"]          # short labels (about 18 characters at most)
caption = "one sentence under the diagram"
```

"Where I've used it" is generated: every project whose stack contains the
name or an alias is listed. Chips with no topic file are plain text and the
build lists them.
