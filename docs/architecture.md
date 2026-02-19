# Open Attend — Architecture Overview

Real-time AI clinical documentation agent built on 5 HAI-DEF models. Listens to doctor-patient conversations, reasons about clinical content mid-visit, and continuously builds structured SOAP notes, medication lists, differential diagnoses, clinical alerts, and billing codes.

## System Architecture

```
Browser (React + TypeScript + Tailwind + Vite)
    |
    |-- WebSocket (raw PCM audio) ---------> FastAPI Backend (Python 3.11+)
    |                                            |
    |                                            |-- AudioBuffer (15s batches, 5s first, flush-at-silence)
    |                                            |
    |                                            |-- Parallel ASR Pipeline (asyncio.gather):
    |                                            |   |-- MedASR 105M (CTC, medical vocabulary)
    |                                            |   |-- Whisper-base (conversational speech)
    |                                            |   '-- Pyannote 3.1 (speaker diarization + embeddings)
    |                                            |
    |                                            |-- Entity-Guided Transcript Merge
    |                                            |   MedASR entities extracted -> LLM corrects Whisper
    |                                            |   output using medical terms as reference
    |                                            |
    |                                            |-- Speaker Registry
    |                                            |   Cosine similarity on Pyannote embeddings
    |                                            |   -> consistent IDs across batches
    |                                            |   -> LLM role assignment (doctor/patient/nurse)
    |                                            |
    |                                            |-- Orchestrator (throttled, Fibonacci cooldowns)
    |                                            |   |-- SOAP drafting (section-specific + verification)
    |                                            |   |-- Medication extraction + interaction checks
    |                                            |   |-- Clinical alerts (red flags, mental health, labs)
    |                                            |   |-- Differential diagnosis
    |                                            |   |-- Order pre-fill with CPT codes
    |                                            |   '-- HeAR audio biomarker analysis
    |                                            |
    |                                            |-- Vision Pipeline (on image upload)
    |                                            |   |-- MedGemma-1.5-4b-it (X-ray, skin, lab reports)
    |                                            |   '-- MedSigLIP-448 + FAISS (similar case retrieval)
    |                                            |
    |                                            |-- FHIR R4 Client
    |                                            |   |-- Pre-visit: import Patient, Meds, Allergies
    |                                            |   '-- Post-visit: export DocumentReference, Conditions
    |                                            |
    |                                            '-- Session Store
    |                                                SQLite (SQLCipher AES-256) write-through cache
    |                                                + in-memory dict for low-latency reads
    |
    |-- REST polling ----------------------> GET /session/{id} (full session state)
    |-- POST /session/{id}/image ----------> Vision pipeline
    |-- POST /session/{id}/finalize -------> ICD-10/CPT extraction + patient summary
    |-- GET/POST /fhir/* -----------------> FHIR R4 sandbox
    '-- Static serving ------------------> Built Vite SPA (frontend/dist/)
```

## HAI-DEF Model Stack

| Model | Params | Role | Runtime |
|---|---|---|---|
| **MedASR** | 105M | Medical speech-to-text. Recognizes drug names, procedures, anatomy that Whisper garbles. | CPU, <2s/chunk |
| **MedGemma-27b-text-it** | 27B | Clinical reasoning engine. SOAP drafting, medication extraction, drug interactions, differential diagnosis, ICD-10/CPT coding, alerts, patient summaries. | GPU (A100/A6000) |
| **MedGemma-1.5-4b-it** | 4B | Medical vision. Analyzes X-rays, skin photos, lab report images. Document understanding for tabular lab data. | GPU (vLLM) |
| **MedSigLIP-448** | 400M | Image retrieval. FAISS similarity search against medical atlas, returns top-3 matching conditions. | CPU/GPU |
| **HeAR** | — | Audio biomarkers. Extracts 512-dim health acoustic embeddings from 2s clips for cough/respiratory pattern detection. | CPU |

## Two Operating Modes

### In-Room (Real-Time Agent)

Audio streams via WebSocket. Dual-ASR transcribes in parallel. Entity-guided merge corrects output. Orchestrator autonomously dispatches tools based on clinical content. Physician sees live sidebar with alerts, medications, differential, and continuously updating SOAP draft. No interaction required.

### Post-Visit (Documentation Agent)

Physician reviews pre-populated SOAP in an editable markdown-rendered view. Actions available:
- Trigger ICD-10/CPT code extraction (auto-runs on finalize)
- Generate plain-language patient summary (6th-grade reading level)
- Upload images for analysis (X-ray, skin, labs)
- Export as PDF or clipboard text for EHR paste
- Export to FHIR R4 as DocumentReference

## Data Flow per 15s Batch

1. `AudioBuffer.flush_at_silence()` scans backward for silence gap, emits single WAV
2. Three `asyncio.create_task()` calls run MedASR, Whisper, Pyannote in parallel
3. MedASR output -> entity extraction (drugs, diagnoses, procedures, anatomy)
4. Entities injected into LLM merge prompt that corrects Whisper transcript
5. Speaker segments merged (adjacent same-speaker, gap < 1.5s)
6. `SpeakerRegistry` matches Pyannote embeddings via cosine similarity -> consistent IDs
7. Role assignment (doctor/patient) runs via LLM once enough context exists
8. `TranscriptChunk` objects built, sent over WebSocket, persisted to session
9. Orchestrator checks per-tool throttles, dispatches due tools concurrently
10. Session state updated in-memory + written through to SQLite
11. Frontend polls `GET /session/{id}` for sidebar updates

## Agentic Tool Dispatch

The orchestrator receives each transcript chunk and decides what to do based on clinical content. Not a fixed pipeline — model-driven tool dispatch.

| Trigger | Tool | Action |
|---|---|---|
| Medication name detected | `extract_medications` -> `check_interactions` | Extract med list, cross-check for interactions |
| Allergy mentioned | `generate_alerts` | Pin persistent alert, cross-reference prescriptions |
| Red-flag symptoms | `generate_alerts` | Surface urgent clinical alert (chest pain, neuro deficits) |
| Mood/sleep/appetite signals | `generate_alerts` | Prompt PHQ-2/GAD-2 screening |
| Order verbalized | `extract_orders` | Pre-fill order with CPT code + clinical indication |
| Exam findings spoken | `draft_full_soap` | Route to SOAP Objective section |
| New symptom identified | `build_differential` | Update running differential diagnosis |
| Every N chunks (cooldown) | `draft_full_soap` | Refresh SOAP draft sections |
| Image uploaded | `analyze_image` + `search_similar` | Vision analysis + FAISS retrieval |
| Lab image uploaded | `extract_lab_values` + `check_lab_alerts` | Parse lab table, flag abnormals |
| Session finalized | `extract_icd10_codes` + `extract_cpt_codes` | Auto-extract billing codes with confidence scores |

### Throttle Strategy

Each tool has a Fibonacci-increasing cooldown schedule to avoid redundant LLM calls while keeping the sidebar responsive:

- Alerts/Medications: 30s, 30s, 60s, 90s, 150s, ...
- Differential: 60s, 60s, 120s, 180s, 300s, ...
- SOAP: refreshes every N chunks (configurable, default 3)

## Key Design Decisions

1. **Dual-ASR + entity-guided merge** — MedASR excels at clinical vocabulary but garbles conversational speech ("Hi Doctor Chen" -> "doctorch"). Whisper handles conversation but misses medical terms. Entity-guided merge extracts medical entities from MedASR output, then an LLM corrects the Whisper transcript using those entities as reference. Best-of-both without naive concatenation.

2. **Buffer-and-batch, not per-utterance** — Audio accumulates server-side for 15s (5s for first batch). CTC models need longer context. Diarization is unreliable on <4s clips. Silence-detection flush prevents splitting mid-word across batches. Cross-batch continuity passes previous turns to the merge call.

3. **Throttled orchestrator with Fibonacci cooldowns** — Per-tool independent cooldowns that increase with each invocation. Early in the visit, tools run frequently to build context. As the visit progresses, intervals lengthen because incremental changes are smaller. Prevents redundant LLM calls without sacrificing responsiveness.

4. **Speaker registry with persistent embeddings** — Pyannote embeddings matched against a cosine-similarity registry. Speakers get consistent IDs across batches. Role assignment runs via MedGemma once enough context exists, then merges duplicate IDs. Registry persists in session store.

5. **Section-specific SOAP with anti-hallucination verification** — Each SOAP section (S/O/A/P) generated independently with strict grounding rules: never fabricate vitals, labs, or exam findings not explicitly stated. Two-pass verification checks every claim against the original transcript. Eval path uses `draft_soap_from_transcript_sectional` + `verify_soap_note`.

6. **FHIR R4 bidirectional integration** — Pre-visit: import Patient, MedicationRequest, AllergyIntolerance, Condition from EHR to pre-populate clinical context. Post-visit: export DocumentReference (LOINC 11506-3: Progress Note) with finalized SOAP + ICD-10 Conditions + ServiceRequests. Auth via SMART on FHIR (OAuth 2.0). Tested against SMART Health IT sandbox.

7. **Auto ICD-10/CPT extraction on finalize** — Billing codes extracted automatically when session transitions to post-visit. Each code includes confidence score and supporting evidence from the transcript. Physician reviews before export.

8. **Privacy-by-design** — All models run locally. No PHI transmitted externally. Session data persists in SQLCipher-encrypted SQLite (AES-256 page encryption). Audio stored locally with configurable TTL. OPENATTEND_DB_KEY env var controls encryption key. Falls back to plain SQLite if pysqlcipher3 not installed.

9. **Prompts are code** — All LLM prompts live in `backend/agents/` as `.md` files, loaded by `agents/__init__.py` and exported as constants. Never inline prompt strings in tool functions. Every prompt specifies return JSON schema. Temperature 0.0 for eval, 0.1-0.2 for production.

10. **Write-through session store** — In-memory dict for sub-millisecond reads (polling), SQLite write-through for persistence. Sessions survive restarts. Properties table stores config (FHIR base URL, etc.).

## FHIR R4 Integration

```
Pre-Visit:
  GET /fhir/patients?name=...    -> search FHIR server
  POST /fhir/import/{patient_id} -> pull Patient + Meds + Allergies + Conditions
                                    -> pre-populate session.patient_context
                                    -> orchestrator starts with existing med list

Post-Visit:
  POST /fhir/export/{session_id} -> build DocumentReference (LOINC 11506-3)
                                    -> attach SOAP note as structured text
                                    -> map ICD-10 codes to Condition resources
                                    -> POST to FHIR server

Auth: SMART on FHIR (OAuth 2.0) for production EHR launches.
Sandbox: https://r4.smarthealthit.org (SMART Health IT public sandbox)
```

## Data Handling

| Data Type | Storage | Encryption | Retention | Access |
|---|---|---|---|---|
| Audio recordings | Local filesystem (~/.openattend/audio/) | AES-256 at rest | Configurable TTL | Session owner only |
| Session notes | SQLite (~/.openattend/sessions.db) | SQLCipher AES-256 page encryption | Persistent until manual delete | Local only |
| Uploaded images | In-memory only | N/A (RAM) | Session lifetime | Session owner only |
| Speaker embeddings | In-memory + SQLite (session JSON) | SQLCipher | Session lifetime | Internal only |
| PHI/PII | Never transmitted externally | All inference local | No cloud API calls | On-premise only |

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript (strict), Tailwind CSS, Vite |
| Backend | FastAPI, asyncio, Python 3.11+, Pydantic v2 |
| ASR | MedASR (HuggingFace), Whisper-base (HuggingFace) |
| Diarization | Pyannote speaker-diarization-3.1 |
| Vision | MedGemma-1.5-4b-it (vLLM), MedSigLIP-448 (HuggingFace), FAISS |
| Audio analysis | HeAR (google/hear-pytorch) |
| LLM inference | vLLM (local, OpenAI-compatible API) |
| LLM reasoning | MedGemma-27b-text-it (primary), configurable via env vars |
| Persistence | SQLite + SQLCipher (pysqlcipher3) |
| EHR integration | FHIR R4 (httpx client), SMART on FHIR sandbox |
| Export | PDF (reportlab), plain text, clipboard |
| Evaluation | WER, MEER, ROUGE, Entity F1, ICD-10/CPT Code F1 |
| Deployment | vast.ai GPU instance (A100/A6000), SSH tunnel |

## Evaluation Results

**SOAP Notes (ACI-Bench, 80 dialogues)**

| Metric | Score |
|---|---|
| ROUGE-1 | 0.517 |
| ROUGE-2 | 0.224 |
| ROUGE-L | 0.299 |
| Entity Precision | 48.5% |
| Entity Recall | 40.4% |
| **Entity F1** | **43.0%** |
| Entity Faithfulness | 65.9% |
| ICD-10 Code F1 | 58.2% (4B model) |
| CPT Code F1 | 73.4% (4B model) |

**Transcription (Fareez OSCE, 25 audio files, 5 specialties, 15s chunked)**

| Model | WER | MEER |
|---|---|---|
| Whisper-base (baseline) | 0.219 | 0.600 |
| MedASR (standalone) | 0.426 | 0.599 |
| Entity-guided merge (MedGemma 27B) | 0.238 | 0.555 |

## Repository Map

```
backend/
  main.py              App entry, routes, WebSocket endpoint
  models.py            Pydantic models (Session, SOAPNote, etc.)
  orchestrator.py      Chunk processing, throttled tool dispatch
  llm.py               LLM client (vLLM / OpenRouter, auto-provider)
  session.py           In-memory + SQLite write-through session store
  transcribe.py        Whisper + MedASR transcription
  transcript_merge.py  Entity-guided merge (MedASR -> Whisper correction)
  diarize.py           Speaker diarization (Pyannote 3.1)
  diarize_align.py     Align diarization segments with transcript
  audio_buffer.py      Audio chunk buffering (15s batches)
  audio_ws.py          WebSocket audio handler
  role_assignment.py   Speaker role inference via LLM
  speaker_registry.py  Embedding-based speaker ID management
  image_tools.py       MedGemma vision + MedSigLIP + FAISS
  hear_tools.py        HeAR audio biomarker embeddings
  fhir_client.py       FHIR R4 patient import/export
  export.py            PDF/text export
  agents/              LLM prompt templates (.md files) + loader
  tools/               Tool functions (meds, alerts, SOAP, coding, etc.)

frontend/src/
  pages/               Route-level components (Landing, Dashboard, InRoom, PostVisit)
  components/          Reusable UI (sidebar, editor, codes, summary)
  hooks/               Data fetching, audio capture, session polling
  api.ts               HTTP + WebSocket client

eval/
  stage1_transcription.py  ASR WER + medical entity recall
  stage2_notes.py          SOAP note quality scoring
  scoring.py               Metrics (WER, MEER, ROUGE, Entity F1, Code F1)
```
