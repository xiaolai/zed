#!/usr/bin/env python3
"""Compose the macOS app icon PNGs from an SVG.

The squircle is generated mathematically rather than exported through
ictool: the macOS 26 renditions all apply the Liquid Glass material, and
its edge highlight shows up as a light seam. n = 5.0 was fitted against
Apple's corner profile, so the silhouette matches without inheriting any
pixels from another icon.
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image

CANVAS, CONTENT, MARGIN, N, SUPERSAMPLE = 1024, 824, 100, 5.0, 4
RESOURCES = Path("crates/zed/resources")


def superellipse(size: int, n: float, ss: int) -> Image.Image:
    big = size * ss
    mask = Image.new("L", (big, big), 0)
    px = mask.load()
    half = big / 2
    for y in range(big):
        ny = abs((y + 0.5 - half) / half)
        if ny > 1:
            continue
        nx = (1 - ny**n) ** (1 / n)
        for x in range(max(0, int(half - nx * half)), min(big, int(half + nx * half))):
            px[x, y] = 255
    return mask.resize((size, size), Image.LANCZOS)


def main(svg: Path) -> None:
    art_png = Path("/tmp/app-icon-art.png")
    subprocess.run(
        ["rsvg-convert", "-w", str(CONTENT), "-h", str(CONTENT), str(svg), "-o", str(art_png)],
        check=True,
    )
    art = Image.open(art_png).convert("RGBA")
    art.putalpha(superellipse(CONTENT, N, SUPERSAMPLE))

    full = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    full.paste(art, (MARGIN, MARGIN), art)
    half = full.resize((512, 512), Image.LANCZOS)

    for name, img in (
        ("app-icon@2x.png", full),
        ("app-icon.png", half),
        ("app-icon-dev@2x.png", full),
        ("app-icon-dev.png", half),
    ):
        img.save(RESOURCES / name)
        print(f"wrote {RESOURCES / name}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "crates/zed/resources/AppIcon.icon/source.svg"))
