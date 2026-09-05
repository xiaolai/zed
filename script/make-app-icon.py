#!/usr/bin/env python3
"""Compose the macOS/Linux app icon PNGs from the glyph SVG plus a solid plate.

The silhouette here is not a free choice. macOS 26 classifies every bundle
icon's alpha before it draws it: a shape it recognises as the system squircle
is masked and drawn edge to edge, and a shape it does not recognise is treated
as a free-form mark -- shrunk to 67.5% and mounted on a light plate, which
shows up as a wide pale frame around the artwork ("squircle jail").

The classifier is undocumented and its tolerance is tight: a plain superellipse
at n = 5.0 (8.4 px RMS from the real shape) is rejected, and so is the best
plain superellipse there is, n = 4.5 at 4.1 px. The geometry below sits at
0.5 px and is accepted, as is the same silhouette eroded or dilated by 2 px.
The constants were fitted against the mask macOS 26 itself applies, recovered
by handing IconServices a full-bleed square and reading back the alpha of what
it returned.

Nothing here can remove the pale seam along the top-left and bottom-right
edges: that is the system's specular edge light, applied to every icon on
macOS 26 over an 18 px band, and it is additive -- a pure black plate still
comes back at luma 163 on the top-left edge. Only the plate's own brightness
changes how much the seam contrasts against it, which is the one lever PLATE
has over it.
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image

CANVAS, CONTENT, MARGIN = 1024, 824, 100

# Apple's corner, measured off the mask macOS 26 applied to a full-bleed square:
# a rounded rectangle whose corner is a superellipse arc.
CORNER_RADIUS_FRACTION = 0.342
CORNER_EXPONENT = 2.8
SUPERSAMPLE = 4

# Where that same system mask's left edge crosses 50% alpha, at y = 102, 142,
# ..., 502 on the 1024 canvas. The generated silhouette is asserted against it
# so the shape cannot drift back out of what macOS 26 recognises.
SYSTEM_MASK_LEFT_EDGE_FIRST_ROW = 102
SYSTEM_MASK_LEFT_EDGE_ROW_STEP = 40
SYSTEM_MASK_LEFT_EDGE = [
    307.68, 185.42, 144.57, 120.72, 108.40, 102.46,
    100.27, 99.48, 99.43, 99.43, 99.43,
]
MAX_SHAPE_RMS_PX = 1.5

PLATE = (55, 60, 69)

RESOURCES = Path("crates/zed/resources")
OUTPUTS = ("app-icon@2x.png", "app-icon.png", "app-icon-dev@2x.png", "app-icon-dev.png")


def squircle(size: int) -> Image.Image:
    """The macOS 26 icon silhouette, antialiased by supersampling."""
    big = size * SUPERSAMPLE
    half = big / 2.0
    radius = CORNER_RADIUS_FRACTION * big
    flat = half - radius
    mask = Image.new("L", (big, big), 0)
    pixels = mask.load()
    for row in range(big):
        distance_from_centre = abs(row + 0.5 - half)
        if distance_from_centre <= flat:
            reach = half
        elif distance_from_centre >= half:
            continue
        else:
            t = (distance_from_centre - flat) / radius
            reach = flat + radius * (1 - t**CORNER_EXPONENT) ** (1 / CORNER_EXPONENT)
        for column in range(max(0, int(half - reach)), min(big, int(half + reach))):
            pixels[column, row] = 255
    return mask.resize((size, size), Image.BOX)


def assert_shape_matches_system(alpha: Image.Image) -> None:
    """Fail loudly if the silhouette drifts away from the shape macOS accepts."""
    columns = alpha.size[0]
    squared_error = 0.0
    for index, expected in enumerate(SYSTEM_MASK_LEFT_EDGE):
        row = SYSTEM_MASK_LEFT_EDGE_FIRST_ROW + index * SYSTEM_MASK_LEFT_EDGE_ROW_STEP
        measured = None
        previous = alpha.getpixel((0, row)) / 255.0
        for column in range(1, columns // 2):
            current = alpha.getpixel((column, row)) / 255.0
            if current >= 0.5:
                measured = column - 1 + (0.5 - previous) / (current - previous)
                break
            previous = current
        if measured is None:
            raise SystemExit(f"silhouette has no edge on row {row}")
        squared_error += (measured - expected) ** 2
    rms = (squared_error / len(SYSTEM_MASK_LEFT_EDGE)) ** 0.5
    if rms > MAX_SHAPE_RMS_PX:
        raise SystemExit(
            f"silhouette is {rms:.2f}px RMS from the macOS 26 mask "
            f"(limit {MAX_SHAPE_RMS_PX}px) -- macOS will treat this as a "
            f"free-form mark and mount it on a light plate"
        )
    print(f"silhouette matches the macOS 26 mask to {rms:.2f}px RMS")


def main(svg: Path) -> None:
    glyph_png = Path("/tmp/app-icon-glyph.png")
    subprocess.run(
        ["rsvg-convert", "-w", str(CONTENT), "-h", str(CONTENT), str(svg),
         "-o", str(glyph_png)],
        check=True,
    )

    art = Image.new("RGBA", (CONTENT, CONTENT), PLATE + (255,))
    art.alpha_composite(Image.open(glyph_png).convert("RGBA"))
    art.putalpha(squircle(CONTENT))

    full = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    full.paste(art, (MARGIN, MARGIN), art)
    assert_shape_matches_system(full.getchannel("A"))

    half = full.resize((512, 512), Image.LANCZOS)
    for name in OUTPUTS:
        image = full if "@2x" in name else half
        image.save(RESOURCES / name)
        print(f"wrote {RESOURCES / name}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "crates/zed/resources/app-icon.svg"))
