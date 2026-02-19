# Scribe -- AI Clinical Documentation Agent

Scribe is a real-time AI clinical documentation assistant that listens to doctor-patient conversations via WebSocket audio streaming, generates SOAP notes, extracts ICD-10/CPT codes, and produces patient summaries. It uses MedGemma models for medical-domain LLM inference and MedASR for transcription.

## Prerequisites

- Python 3.11+
- Node 20+
- ffmpeg
- An OpenAI-compatible LLM server (e.g., vLLM serving MedGemma)

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env  # edit as needed
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The Vite dev server proxies `/api` and `/ws` to the backend.

### Docker

```bash
cp .env.example .env  # edit as needed
docker compose up
```

Backend at `:8000`, frontend at `:3000`.

For a single production image:

```bash
docker build -t scribe .
docker run -p 8000:8000 --env-file .env scribe
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_BASE_URL` | `http://localhost:8080/v1` | OpenAI-compatible endpoint for text LLM |
| `LLM_MODEL` | `google/medgemma-27b-text-it` | Text LLM model name |
| `VISION_LLM_BASE_URL` | `http://localhost:8080/v1` | Endpoint for vision LLM |
| `VISION_LLM_MODEL` | `google/medgemma-1.5-4b-it` | Vision LLM model name |
| `TRANSCRIBE_MODEL` | `google/medasr` | Speech-to-text model |
| `LLM_TIMEOUT` | `30` | LLM request timeout (seconds) |
| `LLM_MAX_TOKENS` | `2048` | Max tokens for LLM responses |
| `LLM_TEMPERATURE` | `0.2` | LLM sampling temperature |
| `SILENCE_THRESHOLD` | `0.005` | Audio silence detection threshold |

## Architecture

```
Browser (React SPA)
  |
  |-- REST (HTTP) --> FastAPI backend
  |-- WebSocket -----> /session/{id}/audio
                          |
                          v
                    Audio Pipeline
                    (VAD -> MedASR -> chunks)
                          |
                          v
                    Orchestrator
                    (SOAP drafting, code extraction,
                     image analysis, summary generation)
                          |
                          v
                    MedGemma LLMs (via OpenAI-compatible API)
```
