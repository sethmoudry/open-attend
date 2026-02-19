#!/usr/bin/env bash
# Scribe — vast.ai instance setup script
# Usage: scp this to the instance, then: bash install.sh
#
# Prereqs: A100 80GB, CUDA 12+, Python 3.10+
# Set HF_TOKEN env var before running (needed for gated MedGemma models)

set -euo pipefail

# ─── Config ───────────────────────────────────────────────────────────────────
MODEL_DIR="/root/models"
BACKEND_DIR="/root/backend"
VLLM_PORT=8000
HF_TOKEN="${HF_TOKEN:-}"

if [ -z "$HF_TOKEN" ]; then
    echo "ERROR: HF_TOKEN not set. Export it first:"
    echo "  export HF_TOKEN=hf_your_token_here"
    echo "  bash install.sh"
    exit 1
fi

echo "=== Scribe Install — $(date) ==="

# ─── 1. Kill any existing model servers ───────────────────────────────────────
echo "[1/6] Killing existing processes..."
pkill -9 -f "vllm" 2>/dev/null || true
pkill -9 -f "uvicorn" 2>/dev/null || true
sleep 3

# ─── 2. System deps ──────────────────────────────────────────────────────────
echo "[2/6] Installing system packages..."
apt-get update -qq && apt-get install -y -qq ffmpeg libsndfile1 > /dev/null 2>&1 || true

# ─── 3. Python deps ──────────────────────────────────────────────────────────
echo "[3/6] Installing Python packages..."
pip install -q --upgrade pip

# vLLM for serving (includes torch/cuda) + bitsandbytes for 4-bit quantization
pip install -q vllm>=0.8.0 bitsandbytes>=0.43.0

# Backend deps (skip torch — already from vllm)
pip install -q \
    fastapi>=0.104.0 \
    "uvicorn[standard]>=0.24.0" \
    websockets>=12.0 \
    python-multipart>=0.0.6 \
    pydantic>=2.0 \
    transformers>=4.40.0 \
    torchaudio>=2.0.0 \
    soundfile>=0.12.0 \
    librosa>=0.10.0 \
    numpy>=1.24.0 \
    httpx>=0.25.0 \
    reportlab>=4.0 \
    faiss-cpu>=1.7.0 \
    Pillow>=10.0.0 \
    pyannote.audio>=3.1.0

# ─── 4. Download models ──────────────────────────────────────────────────────
echo "[4/6] Downloading models (this takes a while first time, cached after)..."
mkdir -p "$MODEL_DIR"

# Login to HuggingFace
python3 -c "from huggingface_hub import login; login(token='$HF_TOKEN')"

# MedGemma-27b-text-it 4-bit (~16GB, via unsloth quantization)
echo "  → MedGemma-27b-text-it (4-bit)..."
python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(
    'unsloth/medgemma-27b-text-it-bnb-4bit',
    local_dir='$MODEL_DIR/medgemma-27b-4bit',
    token='$HF_TOKEN',
    ignore_patterns=['*.gguf', '*.ggml'],
)
print('  ✓ medgemma-27b-4bit downloaded')
"

# MedGemma-1.5-4b-it (vision, ~8GB)
echo "  → MedGemma-1.5-4b-it..."
python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(
    'google/medgemma-1.5-4b-it',
    local_dir='$MODEL_DIR/medgemma-1.5-4b-it',
    token='$HF_TOKEN',
    ignore_patterns=['*.gguf', '*.ggml'],
)
print('  ✓ medgemma-1.5-4b-it downloaded')
"

# ─── 5. Create launch script ─────────────────────────────────────────────────
echo "[5/6] Creating launch scripts..."

cat > /root/start_models.sh << 'LAUNCH'
#!/usr/bin/env bash
# Start vLLM serving both models
set -euo pipefail

MODEL_DIR="/root/models"

# Kill existing
pkill -9 -f "vllm" 2>/dev/null || true
sleep 3

echo "Starting MedGemma-27b-text-it (4-bit) on port 8000..."
nohup python3 -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_DIR/medgemma-27b-4bit" \
    --served-model-name "google/medgemma-27b-text-it" \
    --host 0.0.0.0 \
    --port 8000 \
    --dtype auto \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.45 \
    --max-num-seqs 16 \
    --quantization bitsandbytes \
    --load-format bitsandbytes \
    --trust-remote-code \
    --disable-log-stats \
    > /root/vllm-27b.log 2>&1 &

echo "  PID: $!"
echo "  Log: /root/vllm-27b.log"

echo "Starting MedGemma-1.5-4b-it (vision) on port 8001..."
nohup python3 -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_DIR/medgemma-1.5-4b-it" \
    --served-model-name "google/medgemma-1.5-4b-it" \
    --host 0.0.0.0 \
    --port 8001 \
    --dtype auto \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.35 \
    --max-num-seqs 4 \
    --trust-remote-code \
    --disable-log-stats \
    > /root/vllm-4b.log 2>&1 &

echo "  PID: $!"
echo "  Log: /root/vllm-4b.log"

echo ""
echo "Waiting for models to load..."
for i in $(seq 1 60); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "  ✓ 27b ready (${i}s)"
        break
    fi
    sleep 5
done

for i in $(seq 1 60); do
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo "  ✓ 4b ready (${i}s)"
        break
    fi
    sleep 5
done

echo ""
echo "Models serving. Test with:"
echo "  curl http://localhost:8000/v1/models"
echo "  curl http://localhost:8001/v1/models"
LAUNCH
chmod +x /root/start_models.sh

# Backend launch script
cat > /root/start_backend.sh << 'BACKEND'
#!/usr/bin/env bash
# Start Scribe backend pointing at local vLLM
set -euo pipefail

export LLM_BASE_URL=http://localhost:8000/v1
export LLM_MODEL="google/medgemma-27b-text-it"
export VISION_LLM_BASE_URL=http://localhost:8001/v1
export VISION_LLM_MODEL="google/medgemma-1.5-4b-it"
export LLM_TIMEOUT=60
export LLM_MAX_TOKENS=2048
export LLM_TEMPERATURE=0.2

cd /root/backend
echo "Starting Scribe backend on port 8080..."
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8080 > /root/backend.log 2>&1 &
echo "  PID: $!"
echo "  Log: /root/backend.log"
echo "  Health: http://localhost:8080/health"
BACKEND
chmod +x /root/start_backend.sh

# Quick smoke test script
cat > /root/test_inference.sh << 'TEST'
#!/usr/bin/env bash
# Quick inference test against both models
set -euo pipefail

echo "=== Testing MedGemma-27b (port 8000) ==="
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/medgemma-27b-text-it",
    "messages": [{"role": "user", "content": "Patient reports chest pain radiating to left arm, shortness of breath. List the top 3 differential diagnoses as JSON: {\"differential\": [\"...\", ...]}"}],
    "temperature": 0.2,
    "max_tokens": 256
  }' | python3 -m json.tool

echo ""
echo "=== Testing MedGemma-1.5-4b (port 8001) ==="
curl -s http://localhost:8001/v1/models | python3 -m json.tool

echo ""
echo "=== Testing Backend (port 8080) ==="
curl -s http://localhost:8080/health | python3 -m json.tool 2>/dev/null || echo "Backend not running — start with: bash /root/start_backend.sh"
TEST
chmod +x /root/test_inference.sh

# ─── 6. Summary ──────────────────────────────────────────────────────────────
echo "[6/6] Done!"
echo ""
echo "=== Quick Reference ==="
echo "  Models dir:    $MODEL_DIR"
echo "  Backend dir:   $BACKEND_DIR (upload your code here)"
echo ""
echo "  Start models:  bash /root/start_models.sh"
echo "  Start backend: bash /root/start_backend.sh"
echo "  Test:          bash /root/test_inference.sh"
echo ""
echo "  Logs:"
echo "    tail -f /root/vllm-27b.log"
echo "    tail -f /root/vllm-4b.log"
echo "    tail -f /root/backend.log"
echo ""
echo "  Ports:"
echo "    8000 — MedGemma-27b-text-it (text reasoning)"
echo "    8001 — MedGemma-1.5-4b-it (vision/labs)"
echo "    8080 — Scribe backend API"
