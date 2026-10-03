"""Build automata's logo files.

    python build.py OUT FONT

writes the SVGs into the directory OUT (this one), with the wordmark's letters
as outlines, from FONT, Space Grotesk's variable font
(``SpaceGrotesk[wght].ttf``, from https://github.com/google/fonts, under
ofl/spacegrotesk). It needs fontTools and uharfbuzz. The PNG favicons are
rendered from favicon.svg, e.g. with librsvg:

    for n in 16 32 180 512; do
        rsvg-convert -w $n -h $n favicon.svg -o favicon-$n.png
    done
"""

import pathlib
import sys

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

OUT = pathlib.Path(sys.argv[1])
FONT = pathlib.Path(sys.argv[2])

INK, PAPER = "#141B2D", "#F6F4EE"
ACCENT, ACCENT_ON_DARK = "#4F46E5", "#A5B4FC"

# the mark: Rule 90 grown from one cell for 8 steps (a 15 x 8 grid of 20px
# cells, 2px apart); the seed is the first cell
CELL, GAP = 20, 2
ROWS, WIDTH = 8, 15


def rule90():
    row = [0] * WIDTH
    row[WIDTH // 2] = 1
    cells = []
    for r in range(ROWS):
        cells += [(r, c) for c in range(WIDTH) if row[c]]
        row = [
            (row[c - 1] if c > 0 else 0) ^ (row[c + 1] if c < WIDTH - 1 else 0)
            for c in range(WIDTH)
        ]
    return cells


CELLS = rule90()
MARK_W = WIDTH * (CELL + GAP) - GAP  # 328
MARK_H = ROWS * (CELL + GAP) - GAP  # 174


def cells_svg(color, seed_color, rows=ROWS, dx=0.0, dy=0.0, scale=1.0):
    """The mark's cells as <rect>s (only the first *rows* rows)."""
    out = []
    for r, c in CELLS:
        if r >= rows:
            continue
        x = dx + c * (CELL + GAP) * scale
        y = dy + r * (CELL + GAP) * scale
        fill = seed_color if (r, c) == CELLS[0] else color
        out.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{CELL * scale:.2f}" '
            f'height="{CELL * scale:.2f}" rx="{3 * scale:.2f}" fill="{fill}"/>'
        )
    return "".join(out)


def svg(width, height, body, title):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.2f} '
        f'{height:.2f}" width="{width:.0f}" height="{height:.0f}" role="img">'
        f"<title>{title}</title>{body}</svg>\n"
    )


# the wordmark: "automata" in Space Grotesk 600, -0.03em tracking --------------


def wordmark():
    """The wordmark's path (in font units, y down, baseline at 0), its
    advance width, and the font's ascent and descent."""
    font = TTFont(FONT)
    static = instantiateVariableFont(font, {"wght": 600})
    glyph_set = static.getGlyphSet()
    upem = static["head"].unitsPerEm

    blob = hb.Blob.from_file_path(str(FONT))
    hb_font = hb.Font(hb.Face(blob))
    hb_font.set_variations({"wght": 600})
    buf = hb.Buffer()
    buf.add_str("automata")
    buf.guess_segment_properties()
    hb.shape(hb_font, buf, {"kern": True, "liga": True})

    tracking = -0.03 * upem
    pen = SVGPathPen(glyph_set)
    x = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions, strict=True):
        name = static.getGlyphName(info.codepoint)
        # font units are y up; flip to SVG's y down, baseline at 0
        glyph_set[name].draw(
            TransformPen(pen, (1, 0, 0, -1, x + pos.x_offset, -pos.y_offset))
        )
        x += pos.x_advance + tracking
    hhea = static["hhea"]
    return pen.getCommands(), x - tracking, hhea.ascent, hhea.descent, upem


def lockup(text_color, cell_color, seed_color, title):
    """The mark beside the wordmark, as the mockup has them at 64px: the mark
    0.86em tall, 20/64em before the text, centered on the line box."""
    path, advance, ascent, descent, upem = wordmark()
    size = 64.0  # px per em
    s = size / upem
    mark_h = 55.0
    mark_scale = mark_h / MARK_H
    mark_w = MARK_W * mark_scale
    gap = 20.0
    # a line box 1em tall; with line-height 1, the baseline sits half the
    # (negative) leading below the ascent
    content = (ascent - descent) * s
    baseline = (size - content) / 2 + ascent * s
    width = mark_w + gap + advance * s
    height = size
    mark_y = (height - mark_h) / 2
    body = cells_svg(cell_color, seed_color, dy=mark_y, scale=mark_scale)
    body += (
        f'<path fill="{text_color}" transform="translate({mark_w + gap:.2f} '
        f'{baseline:.2f}) scale({s:.5f})" d="{path}"/>'
    )
    return svg(width, height, body, title)


def favicon(size, title):
    """The first 4 steps on an ink rounded square (as in the mockup at 64)."""
    k = size / 64
    body = f'<rect width="{size}" height="{size}" rx="{14 * k:.2f}" fill="{INK}"/>'
    # the 4 rows span cells 4..10 of 15: 7 cells, 152 x 86
    inner_w, inner_h = 152.0, 86.0
    scale = 44 * k / inner_w
    dx = (size - inner_w * scale) / 2 - 88 * scale
    dy = (size - inner_h * scale) / 2
    body += cells_svg(PAPER, ACCENT_ON_DARK, rows=4, dx=dx, dy=dy, scale=scale)
    return svg(size, size, body, title)


OUT.mkdir(parents=True, exist_ok=True)
files = {
    "automata-mark.svg": svg(MARK_W, MARK_H, cells_svg(INK, ACCENT), "automata"),
    "automata-mark-dark.svg": svg(
        MARK_W, MARK_H, cells_svg(PAPER, ACCENT_ON_DARK), "automata"
    ),
    "automata-mark-ink.svg": svg(MARK_W, MARK_H, cells_svg(INK, INK), "automata"),
    "automata-lockup.svg": lockup(INK, INK, ACCENT, "automata"),
    "automata-lockup-dark.svg": lockup(PAPER, PAPER, ACCENT_ON_DARK, "automata"),
    "favicon.svg": favicon(64, "automata"),
}
for name, text in files.items():
    (OUT / name).write_text(text)
    print(name, len(text))
