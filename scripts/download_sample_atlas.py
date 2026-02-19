#!/usr/bin/env python3
"""Generate a sample atlas of synthetic medical-style images for testing the FAISS pipeline.

Uses Pillow to create placeholder images with labeled conditions — no downloads required.
"""

import argparse
import json
import os
import random
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow is required: pip install Pillow")
    sys.exit(1)

# Synthetic atlas entries: (filename, condition_label, source)
SAMPLE_CONDITIONS = [
    ("melanoma_001.jpg", "Melanoma", "ISIC-2024"),
    ("melanoma_002.jpg", "Melanoma", "ISIC-2024"),
    ("basal_cell_001.jpg", "Basal Cell Carcinoma", "ISIC-2024"),
    ("basal_cell_002.jpg", "Basal Cell Carcinoma", "ISIC-2024"),
    ("psoriasis_001.jpg", "Psoriasis", "DermNet"),
    ("psoriasis_002.jpg", "Psoriasis", "DermNet"),
    ("eczema_001.jpg", "Eczema", "DermNet"),
    ("eczema_002.jpg", "Eczema", "DermNet"),
    ("acne_001.jpg", "Acne Vulgaris", "DermNet"),
    ("acne_002.jpg", "Acne Vulgaris", "DermNet"),
    ("rosacea_001.jpg", "Rosacea", "DermNet"),
    ("squamous_cell_001.jpg", "Squamous Cell Carcinoma", "ISIC-2024"),
    ("vitiligo_001.jpg", "Vitiligo", "DermNet"),
    ("dermatitis_001.jpg", "Contact Dermatitis", "DermNet"),
    ("fungal_001.jpg", "Tinea Corporis", "DermNet"),
]

# Distinct colours per condition so the embeddings aren't identical
CONDITION_COLOURS: dict[str, tuple[int, int, int]] = {
    "Melanoma": (40, 30, 30),
    "Basal Cell Carcinoma": (180, 130, 130),
    "Psoriasis": (200, 80, 80),
    "Eczema": (160, 120, 100),
    "Acne Vulgaris": (220, 180, 170),
    "Rosacea": (210, 140, 140),
    "Squamous Cell Carcinoma": (150, 100, 90),
    "Vitiligo": (240, 235, 230),
    "Contact Dermatitis": (190, 150, 130),
    "Tinea Corporis": (170, 140, 120),
}


def _make_image(path: str, label: str, size: int = 384) -> None:
    """Create a synthetic placeholder image with noise and a label."""
    random.seed(hash(label + os.path.basename(path)) % (2**32))
    base = CONDITION_COLOURS.get(label, (128, 128, 128))

    # Generate pixel data with per-pixel noise
    pixels = []
    for _ in range(size * size):
        r = max(0, min(255, base[0] + random.randint(-30, 30)))
        g = max(0, min(255, base[1] + random.randint(-30, 30)))
        b = max(0, min(255, base[2] + random.randint(-30, 30)))
        pixels.append((r, g, b))

    img = Image.new("RGB", (size, size))
    img.putdata(pixels)

    # Overlay condition label
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    except (IOError, OSError):
        font = ImageFont.load_default()

    # Semi-transparent banner
    banner_h = 36
    for y in range(size - banner_h, size):
        for x in range(size):
            orig = img.getpixel((x, y))
            img.putpixel((x, y), tuple(max(0, c - 60) for c in orig))

    draw.text((8, size - banner_h + 8), label, fill=(255, 255, 255), font=font)
    img.save(path, quality=90)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sample atlas images for FAISS testing")
    parser.add_argument(
        "--output-dir",
        default="data/atlas",
        help="Directory to write sample images (default: data/atlas)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=384,
        help="Image size in pixels (default: 384)",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    metadata = []
    for filename, condition, source in SAMPLE_CONDITIONS:
        path = os.path.join(args.output_dir, filename)
        _make_image(path, condition, size=args.size)
        metadata.append(
            {
                "filename": filename,
                "condition_label": condition,
                "source": source,
            }
        )
        print(f"  created {path} — {condition}")

    meta_path = os.path.join(args.output_dir, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n{len(metadata)} images written to {args.output_dir}/")
    print(f"Metadata saved to {meta_path}")


if __name__ == "__main__":
    main()
