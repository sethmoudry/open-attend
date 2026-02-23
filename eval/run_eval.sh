#!/bin/bash
set -euo pipefail

STAGE="${1:-all}"

echo "============================================"
echo "  MedGemma Scribe — Evaluation Pipeline"
echo "============================================"
echo ""

# Install eval dependencies
echo "[Setup] Installing eval dependencies..."
if command -v poetry &> /dev/null; then
    poetry install --with eval --quiet 2>/dev/null || poetry install --with eval
else
    pip install jiwer rouge-score rapidfuzz httpx --quiet 2>/dev/null || pip install jiwer rouge-score rapidfuzz httpx
fi

# Check backend is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "ERROR: Backend not running at localhost:8000. Start it first."
    echo "  cd backend && uvicorn main:app --host 0.0.0.0 --port 8000"
    exit 1
fi
echo "[Setup] Backend is running."
echo ""

# Download data
echo "[Data] Downloading evaluation datasets..."
python eval/download_data.py
echo ""

# Stage 1
if [ "$STAGE" != "--stage2-only" ]; then
    echo "[Stage 1] Transcription evaluation..."
    python eval/stage1_transcription.py
    echo ""
fi

# Stage 2
if [ "$STAGE" != "--stage1-only" ]; then
    echo "[Stage 2] Note generation evaluation..."
    python eval/stage2_notes.py
    echo ""
fi

# Print summary
echo "============================================"
echo "  Results Summary"
echo "============================================"
python -c "
import json, os
summary_path = 'eval/results/summary.json'
if not os.path.exists(summary_path):
    # Try stage-specific summaries
    for p in ['eval/results/stage1_summary.json', 'eval/results/stage2_summary.json']:
        if os.path.exists(p):
            with open(p) as f:
                print(json.dumps(json.load(f), indent=2))
else:
    with open(summary_path) as f:
        s = json.load(f)

    if 'stage1' in s:
        s1 = s['stage1']
        print(f\"Stage 1 — Transcription (n={s1.get('n_total', '?')})\")
        print(f\"  Merged WER:  {s1.get('merged_wer_mean', 'N/A')}\")
        print(f\"  Merged MEER: {s1.get('merged_meer_mean', 'N/A')}\")
        print(f\"  MedASR WER:  {s1.get('medasr_wer_mean', 'N/A')}\")
        print(f\"  Whisper WER: {s1.get('whisper_wer_mean', 'N/A')}\")
        print()

    if 'stage2' in s:
        s2 = s['stage2']
        print(f\"Stage 2 — Note Generation (n={s2.get('n_encounters', '?')})\")
        print(f\"  SOAP ROUGE-1/2/L: {s2.get('rouge1_mean', 'N/A')} / {s2.get('rouge2_mean', 'N/A')} / {s2.get('rougeL_mean', 'N/A')}\")
        print(f\"  ACI  ROUGE-1/2/L: {s2.get('aci_rouge1_mean', 'N/A')} / {s2.get('aci_rouge2_mean', 'N/A')} / {s2.get('aci_rougeL_mean', 'N/A')}\")
        print(f\"  Entity completeness:    {s2.get('entity_completeness_mean', 'N/A')}\")
        print(f\"  Entity faithfulness:    {s2.get('entity_faithfulness_mean', 'N/A')}\")
        print(f\"  Unsupported rate:       {s2.get('entity_unsupported_rate_mean', 'N/A')}\")
        print(f\"  LLM Judge total (/25):  {s2.get('judge_total_mean', 'N/A')}\")
" 2>/dev/null || echo "(Could not print summary — check eval/results/ manually)"

echo ""
echo "Full results in eval/results/"
