# Scripts

## FAISS Index Build Pipeline

### Prerequisites

```bash
pip install torch transformers Pillow faiss-cpu tqdm numpy
```

### Directory structure

```
data/
  atlas/              # source images + optional metadata.json
  faiss_index.bin     # built FAISS index (IndexFlatIP, cosine sim)
  atlas_metadata.json # ordered metadata matching index rows
scripts/
  build_faiss_index.py
  download_sample_atlas.py
```

### 1. Generate sample atlas (for testing)

```bash
python scripts/download_sample_atlas.py              # writes to data/atlas/
python scripts/download_sample_atlas.py --output-dir data/atlas --size 384
```

Creates 15 synthetic dermatology placeholder images with labelled conditions.

### 2. Build the FAISS index

```bash
python scripts/build_faiss_index.py                   # defaults: data/atlas -> data/
python scripts/build_faiss_index.py \
  --atlas-dir data/atlas \
  --output-dir data \
  --model-name google/siglip-so400m-patch14-384 \
  --batch-size 8 \
  --device cpu
```

Outputs `data/faiss_index.bin` and `data/atlas_metadata.json`.

### CLI reference

| Flag | Default | Description |
|------|---------|-------------|
| `--atlas-dir` | `data/atlas` | Source image directory |
| `--output-dir` | `data` | Where to write index + metadata |
| `--model-name` | `google/siglip-so400m-patch14-384` | HF vision encoder |
| `--batch-size` | `8` | Images per forward pass |
| `--device` | auto | `cuda`, `mps`, or `cpu` |
