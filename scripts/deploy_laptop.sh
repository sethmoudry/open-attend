#!/usr/bin/env bash
# Open Attend Tier 1 Deploy — Laptop (Local, No GPU Required)
#
# Runs the full Open Attend stack locally using Ollama for LLM inference.
# MedGemma 4B-IT runs on CPU via Ollama — no GPU needed.
#
# Recommended hardware:
#   - Apple M1+ with 16GB RAM (best experience)
#   - x86-64 with 16GB RAM (works, slower inference)
#   - ~20GB disk space (Ollama model + app dependencies)
#
# Prerequisites:
#   - Python 3.11+
#   - Ollama installed (brew install ollama or https://ollama.com)
#   - ffmpeg (brew install ffmpeg)
#   - Node.js 18+ (for frontend build)
#
# Usage:
#   bash scripts/deploy_laptop.sh
#
set -euo pipefail

APP_PORT="${APP_PORT:-8000}"
OLLAMA_BASE="${OLLAMA_BASE:-http://localhost:11434}"

echo "=== Open Attend Tier 1 Deploy (Laptop) — $(date) ==="
echo ""

# ---1. Check Ollama
echo "[1/5] Checking Ollama..."
if ! command -v ollama &>/dev/null; then
    echo "  ERROR: Ollama not found. Install it:"
    echo "    macOS:  brew install ollama"
    echo "    Linux:  curl -fsSL https://ollama.com/install.sh | sh"
    echo "    Web:    https://ollama.com"
    exit 1
fi

# Start Ollama if not running
if ! curl -s "$OLLAMA_BASE/api/tags" >/dev/null 2>&1; then
    echo "  Starting Ollama..."
    ollama serve &>/dev/null &
    sleep 3
fi

# ---2. Pull MedGemma model
echo "[2/5] Pulling MedGemma 4B-IT model (first run may take 5-10 min)..."
if ! ollama list 2>/dev/null | grep -q "medgemma"; then
    echo "  Downloading medgemma:4b-it (~3GB)..."
    ollama pull medgemma:4b-it
else
    echo "  Model already downloaded"
fi

# Verify model responds
echo "  Testing model..."
if ollama run medgemma:4b-it "Reply OK" --verbose 2>&1 | head -5 | grep -qi "ok\|OK"; then
    echo "  Model responding"
else
    echo "  WARNING: Model test inconclusive — continuing anyway"
fi

# ---3. Python deps
echo "[3/5] Installing Python dependencies..."
if command -v poetry &>/dev/null; then
    cd "$(dirname "$0")/.."
    poetry install --no-root --no-interaction 2>&1 | tail -3
    PYTHON_CMD="poetry run python3"
else
    echo "  Poetry not found, using pip..."
    pip install -r requirements.txt 2>&1 | tail -3
    PYTHON_CMD="python3"
fi

# ---4. Build frontend (if needed)
echo "[4/5] Building frontend..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ ! -d "$PROJECT_DIR/frontend/dist" ] || [ "$PROJECT_DIR/frontend/src" -nt "$PROJECT_DIR/frontend/dist/index.html" ]; then
    cd "$PROJECT_DIR/frontend"
    npm install --silent 2>&1 | tail -1
    npm run build 2>&1 | tail -3
else
    echo "  Frontend already built (run 'npm run build' in frontend/ to rebuild)"
fi

# ---5. Start app
echo "[5/5] Starting Open Attend..."
cd "$PROJECT_DIR/backend"

export LLM_BASE_URL="$OLLAMA_BASE/v1"
export LLM_MODEL="medgemma:4b-it"
export LLM_API_KEY=""
export VISION_LLM_BASE_URL="$OLLAMA_BASE/v1"
export VISION_LLM_MODEL="medgemma:4b-it"
export LLM_TEMPERATURE="0.1"
export LLM_MAX_TOKENS="2048"

# Cost tracking: local = $0
export LLM_COST_PER_M_INPUT="0"
export LLM_COST_PER_M_OUTPUT="0"

echo ""
echo "=== Open Attend is starting ==="
echo "  LLM:      Ollama (medgemma:4b-it) — local CPU inference"
echo "  App:      http://localhost:$APP_PORT"
echo "  Settings: http://localhost:$APP_PORT/settings"
echo ""
echo "  Press Ctrl+C to stop"
echo ""

$PYTHON_CMD -m uvicorn main:app \
    --host 0.0.0.0 --port "$APP_PORT" \
    --ws-ping-timeout 120
