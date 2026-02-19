#!/usr/bin/env python3
"""Build a FAISS index from medical atlas images using SigLIP embeddings.

Loads images from a source directory, embeds them through a SigLIP vision encoder,
then builds an IndexFlatIP (cosine similarity) FAISS index and saves it alongside
a metadata JSON file.

Usage:
    python scripts/build_faiss_index.py
    python scripts/build_faiss_index.py --atlas-dir data/atlas --batch-size 8
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Prevent OMP/MKL threading segfaults on macOS when combined with multiprocessing
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np

try:
    import faiss
except ImportError:
    print("FAISS is required: pip install faiss-cpu  (or faiss-gpu)")
    sys.exit(1)

try:
    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, SiglipVisionModel
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install torch transformers Pillow")
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    # Graceful fallback — just iterate without a progress bar
    def tqdm(it, **_kw):  # type: ignore[misc]
        return it


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}


def gather_images(atlas_dir: str) -> list[Path]:
    """Return a deterministically-sorted list of image paths."""
    atlas = Path(atlas_dir)
    if not atlas.is_dir():
        print(f"Error: atlas directory not found: {atlas_dir}")
        sys.exit(1)

    paths = sorted(
        p for p in atlas.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
    )
    return paths


def load_metadata(atlas_dir: str) -> dict[str, dict]:
    """Load optional metadata.json from the atlas directory, keyed by filename."""
    meta_path = Path(atlas_dir) / "metadata.json"
    if not meta_path.exists():
        return {}
    with open(meta_path) as f:
        entries = json.load(f)
    return {e["filename"]: e for e in entries}


def embed_images(
    image_paths: list[Path],
    model_name: str,
    batch_size: int,
    device: str,
) -> np.ndarray:
    """Embed images and return L2-normalised feature matrix (N x D)."""
    print(f"Loading vision model: {model_name}")
    processor = AutoImageProcessor.from_pretrained(model_name)
    model = SiglipVisionModel.from_pretrained(model_name).to(device).eval()

    all_embeddings: list[np.ndarray] = []
    skipped = 0
    valid_paths: list[Path] = []

    for p in tqdm(image_paths, desc="Embedding images"):
        try:
            img = Image.open(p).convert("RGB")
        except Exception as exc:
            print(f"  WARNING: skipping {p.name} — {exc}")
            skipped += 1
            continue

        inputs = processor(images=[img], return_tensors="pt")
        pixel_values = inputs["pixel_values"].to(device)

        with torch.no_grad():
            outputs = model(pixel_values=pixel_values)

        # Use pooler_output if available, else mean-pool last_hidden_state
        if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
            feats = outputs.pooler_output
        else:
            feats = outputs.last_hidden_state.mean(dim=1)

        feats = feats.cpu().numpy().astype(np.float32)

        # L2-normalise so IndexFlatIP computes cosine similarity
        norm = np.linalg.norm(feats, axis=1, keepdims=True)
        norm = np.where(norm == 0, 1, norm)
        feats = feats / norm

        all_embeddings.append(feats)
        valid_paths.append(p)

    if skipped:
        print(f"  Skipped {skipped} unreadable image(s)")

    return np.vstack(all_embeddings), valid_paths


def build_index(embeddings: np.ndarray) -> faiss.Index:
    """Build a flat inner-product FAISS index."""
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    return index


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build FAISS index from medical atlas images"
    )
    parser.add_argument(
        "--atlas-dir",
        default="data/atlas",
        help="Directory containing atlas images (default: data/atlas)",
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Directory to write index and metadata (default: data)",
    )
    parser.add_argument(
        "--model-name",
        default="google/siglip-so400m-patch14-384",
        help="HuggingFace model for image embeddings (default: google/siglip-so400m-patch14-384)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Batch size for embedding (default: 8)",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Torch device (default: auto-detect cuda/mps/cpu)",
    )
    args = parser.parse_args()

    # Auto-detect device
    if args.device is None:
        if torch.cuda.is_available():
            device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
    else:
        device = args.device
    print(f"Device: {device}")

    # Gather images
    image_paths = gather_images(args.atlas_dir)
    if not image_paths:
        print("No images found. Run scripts/download_sample_atlas.py first.")
        sys.exit(1)
    print(f"Found {len(image_paths)} images in {args.atlas_dir}/")

    # Load optional metadata
    meta_lookup = load_metadata(args.atlas_dir)

    # Embed
    t0 = time.time()
    embeddings, image_paths = embed_images(image_paths, args.model_name, args.batch_size, device)
    elapsed = time.time() - t0
    print(f"Embedding complete: {embeddings.shape[0]} vectors, dim={embeddings.shape[1]}, {elapsed:.1f}s")

    # Build index
    index = build_index(embeddings)

    # Prepare output
    os.makedirs(args.output_dir, exist_ok=True)
    index_path = os.path.join(args.output_dir, "faiss_index.bin")
    meta_path = os.path.join(args.output_dir, "atlas_metadata.json")

    faiss.write_index(index, index_path)

    # Build metadata list (preserves deterministic order matching the index)
    atlas_metadata = []
    for p in image_paths:
        entry = meta_lookup.get(p.name, {})
        atlas_metadata.append(
            {
                "filename": p.name,
                "condition_label": entry.get("condition_label", "Unknown"),
                "source": entry.get("source", "Unknown"),
                "embedding_dim": int(embeddings.shape[1]),
            }
        )

    with open(meta_path, "w") as f:
        json.dump(atlas_metadata, f, indent=2)

    # Summary
    print("\n--- Summary ---")
    print(f"  Images processed : {len(atlas_metadata)}")
    print(f"  Embedding dim    : {embeddings.shape[1]}")
    print(f"  Index size       : {os.path.getsize(index_path) / 1024:.1f} KB")
    print(f"  Index path       : {index_path}")
    print(f"  Metadata path    : {meta_path}")


if __name__ == "__main__":
    main()
