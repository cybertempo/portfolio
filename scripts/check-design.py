#!/usr/bin/env python3
"""[LAPTOP] python3 scripts/check-design.py

Build/gate every saved palette × minimap in a disposable local directory.
Does not change site.toml or dist/. Browser interaction is checked separately.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from hashlib import sha256
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import tomllib
import re
import render


def main():
    content = tomllib.loads(render.CONTENT.read_text())
    palettes = sorted(render.PALETTES.glob('*.toml'))
    modules = sorted(p for p in (render.SRC / 'minimaps').iterdir() if p.is_dir())
    sources = [render.CONTENT, *palettes, *(p for module in modules for p in module.iterdir() if p.is_file())]
    before = {p: sha256(p.read_bytes()).digest() for p in sources}
    for invalid in ('../rift', 'missing-minimap', '/rift'):
        try:
            render.load_minimap(invalid)
        except render.Refuse:
            pass
        else:
            raise AssertionError(f'Invalid module accepted: {invalid}')
    print('controls: unsafe/missing modules refused')
    with TemporaryDirectory(prefix='.design-check-', dir=render.ROOT / 'build') as temp:
        render.DIST = Path(temp) / 'dist'
        for module in modules:
            for palette in palettes:
                candidate = deepcopy(content)
                candidate['design'].update(palette=palette.stem, minimap=module.name)
                with redirect_stdout(StringIO()):
                    page, _, unlinked, topics = render.render(candidate)
                    assert not unlinked
                    render.write_dist(page, topics)
                    render.gate_dist()
                assert '{{' not in page
                assert 'minimap.css' in page and 'minimap.js' in page
                assert (render.DIST / 'minimap.js').read_text() == (module / 'behavior.js').read_text()
                assert len(list(render.DIST.rglob('*.html'))) == len(topics) + 1
                print(f'PASS {palette.stem} / {module.name}')
    assert before == {p: sha256(p.read_bytes()).digest() for p in sources}
    print('Saved palettes and selection unchanged; all combinations passed.')


if __name__ == '__main__':
    main()
