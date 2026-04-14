#!/usr/bin/env python3
"""Composite a PDF image layer with its soft mask onto a white background."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Composite a PDF image layer and its smask into a visible RGB image."
    )
    parser.add_argument("image", help="Color image extracted from the PDF.")
    parser.add_argument("smask", help="Soft-mask image extracted from the PDF.")
    parser.add_argument("output", help="Output image path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    image = Image.open(args.image).convert("RGBA")
    smask = Image.open(args.smask).convert("L")
    if image.size != smask.size:
        raise ValueError(
            f"Image and smask size mismatch: {image.size} != {smask.size}"
        )

    image.putalpha(smask)
    background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    background.alpha_composite(image)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    background.convert("RGB").save(output)
    print(f"Wrote composited image to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
