#!/usr/bin/env bash
# Open Attend Tier 3 Deploy — Hospital (Google Cloud Vertex AI)
#
# Deploys Open Attend with Vertex AI managed endpoints for LLM inference.
# Designed for hospital-scale deployment (50+ physicians).
#
# Prerequisites:
#   - gcloud CLI authenticated with a project that has a BAA signed
#   - Vertex AI API enabled
#   - MedGemma models deployed to Vertex AI Model Garden endpoints
#   - Python 3.11+, ffmpeg
#
# Cost estimate (50 physicians):
#   - MedGemma-27B: 2× A100 80GB dedicated endpoint ~$9,000/mo
#   - MedGemma-4B + auxiliary: GKE GPU node pool (L4) ~$800/mo
#   - Total: ~$10,000/mo (~$200/physician/mo)
#
# Usage:
#   export VERTEX_PROJECT=my-project
#   export VERTEX_REGION=us-central1
#   export VERTEX_TEXT_ENDPOINT=projects/xxx/locations/xxx/endpoints/xxx
#   export VERTEX_VISION_ENDPOINT=projects/xxx/locations/xxx/endpoints/xxx
#   bash scripts/deploy_vertex.sh
#
set -euo pipefail

VERTEX_PROJECT="${VERTEX_PROJECT:?Set VERTEX_PROJECT}"
VERTEX_REGION="${VERTEX_REGION:-us-central1}"
VERTEX_TEXT_ENDPOINT="${VERTEX_TEXT_ENDPOINT:?Set VERTEX_TEXT_ENDPOINT (Vertex AI endpoint for MedGemma-27B)}"
VERTEX_VISION_ENDPOINT="${VERTEX_VISION_ENDPOINT:-$VERTEX_TEXT_ENDPOINT}"
APP_PORT="${APP_PORT:-8000}"

echo "=== Open Attend Tier 3 Deploy (Vertex AI) — $(date) ==="
echo "  Project:  $VERTEX_PROJECT"
echo "  Region:   $VERTEX_REGION"
echo ""

# ---1. Verify gcloud auth
echo "[1/4] Verifying Google Cloud authentication..."
if ! gcloud auth print-access-token &>/dev/null; then
    echo "  ERROR: Not authenticated. Run: gcloud auth login"
    exit 1
fi

GCLOUD_TOKEN=$(gcloud auth print-access-token)
echo "  Authenticated as: $(gcloud config get-value account 2>/dev/null)"

# ---2. Check Vertex AI endpoints
echo "[2/4] Checking Vertex AI endpoints..."

TEXT_BASE="https://${VERTEX_REGION}-aiplatform.googleapis.com/v1/${VERTEX_TEXT_ENDPOINT}"
VISION_BASE="https://${VERTEX_REGION}-aiplatform.googleapis.com/v1/${VERTEX_VISION_ENDPOINT}"

# Test text endpoint
if curl -sf -H "Authorization: Bearer $GCLOUD_TOKEN" "${TEXT_BASE}:predict" \
    -d '{"instances":[{"prompt":"test"}]}' >/dev/null 2>&1; then
    echo "  Text endpoint: OK"
else
    echo "  WARNING: Text endpoint not responding — check deployment status"
fi

# ---3. Install dependencies
echo "[3/4] Installing dependencies..."
cd "$(dirname "$0")/.."
poetry install --no-root --no-interaction 2>&1 | tail -3

# Build frontend
if [ ! -d "frontend/dist" ]; then
    cd frontend && npm install --silent && npm run build 2>&1 | tail -3 && cd ..
fi

# ---4. Start app
echo "[4/4] Starting Open Attend..."
cd backend

# Vertex AI uses OpenAI-compatible endpoint format
export LLM_BASE_URL="${TEXT_BASE}/openapi"
export LLM_MODEL="google/medgemma-27b-text-it"
export LLM_API_KEY="$GCLOUD_TOKEN"
export VISION_LLM_BASE_URL="${VISION_BASE}/openapi"
export VISION_LLM_MODEL="google/medgemma-1.5-4b-it"

# Vertex AI pricing (approximate per-token)
export LLM_COST_PER_M_INPUT="0.30"
export LLM_COST_PER_M_OUTPUT="0.90"

# HIPAA: Generate encryption key for local session storage
if [ -z "${OPENATTEND_DB_KEY:-}" ]; then
    export OPENATTEND_DB_KEY=$(openssl rand -hex 32)
    echo "  Generated OPENATTEND_DB_KEY"
fi

mkdir -p ~/.openattend/audio/

echo ""
echo "=== Open Attend is starting ==="
echo "  LLM:       Vertex AI (MedGemma-27B)"
echo "  Vision:    Vertex AI (MedGemma-4B)"
echo "  Project:   $VERTEX_PROJECT"
echo "  App:       http://localhost:$APP_PORT"
echo ""

poetry run python3 -m uvicorn main:app \
    --host 0.0.0.0 --port "$APP_PORT" \
    --ws-ping-timeout 120
