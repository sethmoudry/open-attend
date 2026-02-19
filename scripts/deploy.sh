#!/usr/bin/env bash
# Open Attend Tier 2 Deploy — Small Clinic (vast.ai / GCE GPU Instance)
#
# Runs the full stack on a single GPU instance (A100 80GB or A6000 48GB).
# Two vLLM processes: text LLM (27B BNB 4-bit) + vision LLM (4B FP16).
# Cost: ~$780/month on GCE with 1-year commit, ~$150/month on vast.ai spot.
#
# Recommended hardware:
#   - NVIDIA A100 80GB (best) or A6000 48GB
#   - 64GB+ system RAM
#   - 200GB disk
#
# Usage:
#   export HF_TOKEN=hf_xxx OPENROUTER_API_KEY=sk-or-xxx
#   bash scripts/deploy.sh
set -euo pipefail

HF_TOKEN="${HF_TOKEN:?Set HF_TOKEN}"
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"

VLLM_VENV="/root/vllm_venv"

# Text LLM -- MedGemma 27B with BNB 4-bit quantization
VLLM_MODEL="${VLLM_MODEL:-google/medgemma-27b-text-it}"
VLLM_PORT=8080

# Vision LLM -- MedGemma 4B multimodal
VISION_MODEL="${VISION_MODEL:-google/medgemma-1.5-4b-it}"
VISION_PORT=8081

APP_PORT=8000

echo "=== Open Attend Deploy -- $(date) ==="

# ---1. System deps (includes libsqlcipher-dev for SQLCipher encrypted DB)
echo "[1/6] System packages..."
apt-get update -qq && apt-get install -y -qq ffmpeg libsndfile1 libsqlcipher-dev > /dev/null 2>&1 || true

# Generate DB encryption key if not already set.
# SQLCipher uses this to AES-256 encrypt the sessions database at rest.
if [ -z "${OPENATTEND_DB_KEY:-}" ]; then
    export OPENATTEND_DB_KEY=$(openssl rand -hex 32)
    echo "  Generated OPENATTEND_DB_KEY (store this securely for persistence across deploys)"
fi

# Create local data directories
mkdir -p ~/.openattend/audio/

# ---2. App deps via Poetry ----------------------------------------------
echo "[2/6] App deps (poetry)..."
pip install -q pipx 2>/dev/null || true
pipx install poetry 2>/dev/null || true
export PATH="$PATH:/root/.local/bin"

cd /root
poetry install --no-root --no-interaction 2>&1 | tail -5

# ---2b. Download ICD-10-CM lookup table if not present
if [ ! -f /root/backend/data/icd10cm_codes.tsv ]; then
    echo "  Downloading ICD-10-CM lookup table..."
    poetry run python3 /root/scripts/download_icd10.py || echo "  WARNING: ICD-10 download failed (non-fatal)"
fi

# ---3. vLLM venv (torch 2.9.x, isolated) ------------------------------
echo "[3/6] vLLM venv (torch 2.9)..."
if [ ! -d "$VLLM_VENV" ]; then
    python3 -m venv "$VLLM_VENV"
fi
"$VLLM_VENV/bin/pip" install -q --upgrade pip
"$VLLM_VENV/bin/pip" install -q vllm bitsandbytes

# ---4. Start vLLM -- Text LLM (27B BNB 4-bit) --------------------------
echo "[4/6] Starting vLLM text LLM ($VLLM_MODEL on :$VLLM_PORT)..."
pkill -9 -f "vllm.entrypoints" 2>/dev/null || true
pkill -9 -f "VLLM::EngineCore" 2>/dev/null || true
pkill -9 -f "from vllm" 2>/dev/null || true
sleep 3

HF_TOKEN="$HF_TOKEN" nohup "$VLLM_VENV/bin/python3" \
    -m vllm.entrypoints.openai.api_server \
    --model "$VLLM_MODEL" \
    --quantization bitsandbytes \
    --load-format bitsandbytes \
    --dtype bfloat16 \
    --port "$VLLM_PORT" \
    --max-model-len 65536 \
    --gpu-memory-utilization 0.55 \
    > /root/vllm.log 2>&1 &
echo "  Text LLM PID: $!"

# ---5. Start vLLM -- Vision LLM (4B FP16)
echo "[5/6] Starting vLLM vision LLM ($VISION_MODEL on :$VISION_PORT)..."
sleep 5  # stagger startup to avoid GPU contention

HF_TOKEN="$HF_TOKEN" nohup "$VLLM_VENV/bin/python3" \
    -m vllm.entrypoints.openai.api_server \
    --model "$VISION_MODEL" \
    --dtype bfloat16 \
    --port "$VISION_PORT" \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.20 \
    > /root/vllm_vision.log 2>&1 &
echo "  Vision LLM PID: $!"

echo "  Waiting for text LLM..."
for i in $(seq 1 120); do
    if curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; then
        echo "  Text LLM ready (${i}s)"
        break
    fi
    sleep 5
done

if ! curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; then
    echo "  WARNING: Text LLM not ready yet. Check /root/vllm.log"
fi

echo "  Waiting for vision LLM..."
for i in $(seq 1 90); do
    if curl -s "http://localhost:$VISION_PORT/health" > /dev/null 2>&1; then
        echo "  Vision LLM ready (${i}s)"
        break
    fi
    sleep 5
done

if ! curl -s "http://localhost:$VISION_PORT/health" > /dev/null 2>&1; then
    echo "  WARNING: Vision LLM not ready yet. Check /root/vllm_vision.log"
fi

# ---6. Start app ------------------------------------------------------
echo "[6/6] Starting app server..."
pkill -9 -f "uvicorn main:app" 2>/dev/null || true
sleep 1

cd /root/backend
LLM_BASE_URL="http://localhost:$VLLM_PORT/v1" \
LLM_MODEL="$VLLM_MODEL" \
LLM_API_KEY="none" \
VISION_LLM_BASE_URL="http://localhost:$VISION_PORT/v1" \
VISION_LLM_MODEL="$VISION_MODEL" \
HF_TOKEN="$HF_TOKEN" \
OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
nohup poetry run python3 -m uvicorn main:app \
    --host 0.0.0.0 --port "$APP_PORT" \
    --ws-ping-timeout 120 \
    > /root/server.log 2>&1 &
echo "  App PID: $!"

sleep 5
echo ""
echo "=== Deploy complete ==="
echo "  Text LLM:   http://localhost:$VLLM_PORT   (log: /root/vllm.log)"
echo "  Vision LLM: http://localhost:$VISION_PORT  (log: /root/vllm_vision.log)"
echo "  App:        http://localhost:$APP_PORT     (log: /root/server.log)"
echo ""
echo "  SSH tunnel: ssh -p PORT -L $APP_PORT:localhost:$APP_PORT root@HOST"
echo "  Then open:  http://localhost:$APP_PORT"
