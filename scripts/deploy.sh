#!/usr/bin/env bash
# Scribe deploy script for vast.ai GPU instances.
# Two-venv approach: app (torch 2.4) + vLLM (torch 2.9) — isolated.
#
# Usage:
#   export HF_TOKEN=hf_xxx OPENROUTER_API_KEY=sk-or-xxx
#   bash scripts/deploy.sh
set -euo pipefail

HF_TOKEN="${HF_TOKEN:?Set HF_TOKEN}"
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"

APP_VENV="/root/app_venv"
VLLM_VENV="/root/vllm_venv"
VLLM_MODEL="${VLLM_MODEL:-MedGemmaImpact/medgemma-1.5-4b-it-awq}"
VLLM_PORT=8080
APP_PORT=8000

echo "=== Scribe Deploy — $(date) ==="

# ─── 1. System deps ─────────────────────────────────────────────────────
echo "[1/5] System packages..."
apt-get update -qq && apt-get install -y -qq ffmpeg libsndfile1 > /dev/null 2>&1 || true

# ─── 2. App venv (torch 2.4.x + pyannote + MedASR transformers) ────────
echo "[2/5] App venv (torch <2.5)..."
if [ ! -d "$APP_VENV" ]; then
    python3 -m venv "$APP_VENV"
fi
"$APP_VENV/bin/pip" install -q --upgrade pip
# Install torch/torchaudio FIRST to prevent other packages from pulling newer versions
"$APP_VENV/bin/pip" install -q torch==2.4.1 torchaudio==2.4.1
"$APP_VENV/bin/pip" install -q -r /root/backend/requirements.txt

# ─── 3. vLLM venv (torch 2.9.x, isolated) ──────────────────────────────
echo "[3/5] vLLM venv (torch 2.9)..."
if [ ! -d "$VLLM_VENV" ]; then
    python3 -m venv "$VLLM_VENV"
fi
"$VLLM_VENV/bin/pip" install -q --upgrade pip
"$VLLM_VENV/bin/pip" install -q vllm

# ─── 4. Start vLLM ─────────────────────────────────────────────────────
echo "[4/5] Starting vLLM ($VLLM_MODEL)..."
pkill -9 -f "vllm.entrypoints" 2>/dev/null || true
pkill -9 -f "VLLM::EngineCore" 2>/dev/null || true
pkill -9 -f "from vllm" 2>/dev/null || true
sleep 3

HF_TOKEN="$HF_TOKEN" nohup "$VLLM_VENV/bin/python3" \
    -m vllm.entrypoints.openai.api_server \
    --model "$VLLM_MODEL" \
    --dtype bfloat16 \
    --port "$VLLM_PORT" \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.90 \
    > /root/vllm.log 2>&1 &
echo "  vLLM PID: $!"

echo "  Waiting for vLLM..."
for i in $(seq 1 90); do
    if curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; then
        echo "  vLLM ready (${i}s)"
        break
    fi
    sleep 5
done

if ! curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; then
    echo "  WARNING: vLLM not ready yet. Check /root/vllm.log"
fi

# ─── 5. Start app ──────────────────────────────────────────────────────
echo "[5/5] Starting app server..."
pkill -9 -f "uvicorn main:app" 2>/dev/null || true
sleep 1

cd /root/backend
LLM_BASE_URL="http://localhost:$VLLM_PORT/v1" \
LLM_MODEL="$VLLM_MODEL" \
LLM_API_KEY="none" \
HF_TOKEN="$HF_TOKEN" \
OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
nohup "$APP_VENV/bin/python3" -m uvicorn main:app \
    --host 0.0.0.0 --port "$APP_PORT" \
    --ws-ping-timeout 120 \
    > /root/server.log 2>&1 &
echo "  App PID: $!"

sleep 5
echo ""
echo "=== Deploy complete ==="
echo "  vLLM:  http://localhost:$VLLM_PORT  (log: /root/vllm.log)"
echo "  App:   http://localhost:$APP_PORT   (log: /root/server.log)"
echo ""
echo "  SSH tunnel: ssh -p PORT -L $APP_PORT:localhost:$APP_PORT root@HOST"
echo "  Then open:  http://localhost:$APP_PORT"
