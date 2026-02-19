# Open Attend — Agentic Clinical Decision Support and Documentation

**Contact:** sethmoudry@gmail.com | codyheslep@gmail.com | okpoyeenzo@gmail.com

Open Attend listens to doctor-patient conversations in real time and autonomously generates structured clinical documentation — SOAP notes, ICD-10/CPT codes, medication lists, clinical alerts, and patient summaries — all powered by open-weight MedGemma models with zero external API dependencies.

![MedGemma](https://img.shields.io/badge/MedGemma-27B%20%7C%204B-blue) ![Python](https://img.shields.io/badge/Python-3.11+-green) ![React](https://img.shields.io/badge/React-18-61DAFB) ![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688)

---

## Features

### Real-Time In-Room Agent
- **Dual-ASR pipeline** — MedASR (medical vocabulary) + Whisper (conversational), merged via LLM entity-guided fusion
- **Speaker diarization** — Pyannote 3.1 with persistent speaker embeddings for doctor/patient/nurse identification
- **Live SOAP drafting** — Section-by-section generation with anti-hallucination verification pass
- **Clinical alerts** — Drug interactions, allergy flags, PHQ-2/GAD-2 mental health screening prompts
- **Medication extraction** — Structured parsing with interaction checking
- **ICD-10/CPT coding** — Automatic code extraction with confidence scores
- **Differential diagnosis** — Running differential updated as conversation progresses
- **Medical image analysis** — X-ray, dermatology, lab report parsing via MedGemma vision model
- **Order pre-fill** — Captures verbal orders with CPT codes

### Post-Visit Documentation
- Physician review/edit of pre-populated SOAP notes
- Plain-language patient summary (6th-grade reading level)
- PDF export

### Privacy & Security
- All models are open-weight — no data leaves your infrastructure
- SQLCipher AES-256 encrypted session database
- Zero vendor lock-in

---

## MedGemma Models

| Model | Role | Serving |
|---|---|---|
| **MedGemma 27B Text IT** | Clinical reasoning, SOAP drafting, coding, alerts | vLLM + BNB 4-bit quantization |
| **MedGemma 1.5 4B IT** | Medical image analysis (X-ray, skin, labs) | vLLM FP16 |
| **MedASR** (105M) | Medical speech-to-text (CTC) | HuggingFace Transformers / MLX |

Supporting models: Whisper-base (conversational ASR), Pyannote 3.1 (diarization), HeAR (audio biomarkers, optional).

---

## Tech Stack

- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS
- **Backend:** FastAPI + Uvicorn (async-first, WebSocket streaming)
- **ML Serving:** vLLM (OpenAI-compatible API)
- **Database:** SQLite + SQLCipher (encrypted at rest)
- **Audio:** 15-second batched streaming with silence-detection flush

---

## Quick Start (Local Development)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install && npm run dev
```

Open http://localhost:3000. Vite proxies `/api` and `/ws` to the backend.

### Docker

```bash
docker compose up   # Backend :8000, Frontend :3000
```

---

## GPU Server Deployment (vast.ai)

**Requirements:** A100 80GB (recommended) or RTX A6000 48GB

### 1. Rent & connect

```bash
vastai search offers 'gpu_name=A100_SXM4 gpu_ram>=80 reliability>0.95 dph<2.0' -o 'dph+'
vastai create instance <ID> --image vastai/pytorch --disk 200 --ssh
ssh -p <PORT> root@<HOST>
```

### 2. Upload & deploy

```bash
# From local machine
scp -rP <PORT> backend/ scripts/ pyproject.toml poetry.lock root@<HOST>:/root/

# On the server
export HF_TOKEN=hf_xxx
bash scripts/deploy.sh
```

The deploy script handles everything:
1. Installs system deps (ffmpeg, libsqlcipher)
2. Sets up app venv (Poetry) + isolated vLLM venv (torch 2.9)
3. Launches **MedGemma 27B** text LLM on `:8080` (BNB 4-bit, 55% GPU)
4. Launches **MedGemma 4B** vision LLM on `:8081` (FP16, 20% GPU)
5. Starts FastAPI app on `:8000`

### 3. Access

```bash
ssh -p <PORT> -L 8000:localhost:8000 root@<HOST>
# Open http://localhost:8000
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_BASE_URL` | `http://localhost:8080/v1` | Text LLM endpoint |
| `LLM_MODEL` | `google/medgemma-27b-text-it` | Text LLM model |
| `VISION_LLM_BASE_URL` | `http://localhost:8081/v1` | Vision LLM endpoint |
| `VISION_LLM_MODEL` | `google/medgemma-1.5-4b-it` | Vision LLM model |
| `TRANOPENATTEND_MODEL` | `google/medasr` | ASR model |
| `LLM_TIMEOUT` | `300` | LLM request timeout (seconds) |
| `LLM_MAX_TOKENS` | `2048` | Max generation tokens |
| `LLM_TEMPERATURE` | `0.2` | Sampling temperature |
| `HF_TOKEN` | — | HuggingFace token (model download) |
| `OPENATTEND_DB_KEY` | auto-generated | SQLCipher encryption key |

---

## Architecture

```
Browser (React SPA)
  |
  |-- REST API ---------> FastAPI
  |-- WebSocket --------> /session/{id}/audio
                             |
                             v
                       Audio Pipeline
                       MedASR + Whisper --> LLM Entity Merge
                       Pyannote Diarization
                             |
                             v
                       Throttled Orchestrator
                       (independent cooldowns per tool)
                             |
        +--------+--------+--------+--------+--------+
        |        |        |        |        |        |
      SOAP    Meds    Alerts   Codes   Images   Dx
      draft   extract  flags   ICD/CPT  vision  diff
        |        |        |        |        |        |
        v        v        v        v        v        v
                    MedGemma LLMs (via vLLM)
```
