### Open Attend — Agentic Clinical Decision Support and Documentation

### Team

Seth Moudry — ML engineer, full-stack developer, sole builder. Every line of code agent-generated.

### Problem Statement

**The documentation crisis is measurable.** For every 1 hour of direct patient care, physicians spend 2 hours on EHR paperwork (Sinsky et al., *Annals of Internal Medicine*, 2016). 49.2% of a physician's workday goes to desk work; only 27% goes to patients. After clinic hours, physicians average 86 minutes per night of "pajama time" completing notes (Arndt et al., 2017). The downstream cost: 43.2% physician burnout rate nationally, $4.6 billion in annual turnover, and 20% of malpractice cases traced to documentation failures (CRICO, 2024).

**The market is locked behind closed doors.** Ambient AI scribe products (Nuance DAX, Abridge, Nabla) charge $300–600/month per physician, run entirely through proprietary cloud APIs, and offer zero transparency into how notes are generated. No open-weight alternative exists. Physicians in resource-constrained settings, rural clinics, international health systems, and academic institutions are priced out or blocked by data residency requirements.

**The unmet need is timing.** Every commercial solution generates notes *after* the visit ends. The physician still carries the cognitive burden of remembering clinical details. A 2024 Kaiser Permanente study showed even the best AI scribes only reduce documentation time by ~20% — because the bottleneck isn't writing speed, it's the context switch between patient care and documentation. Documentation should happen *while* the visit is happening, not after.

**If deployed to 155,000 US primary care physicians at 30 min/day savings, Open Attend would recover 77,500 physician-hours daily — equivalent to adding ~10,000 full-time physicians to the workforce.** At $45,000–$60,000/year per human scribe replaced, the cost savings for a single health system are measured in millions.

### Overall Solution

Open Attend is a real-time in-room documentation agent built on four HAI-DEF models that listens to doctor-patient conversations, reasons about clinical content as it hears it, and continuously builds structured documentation. By the time the visit ends, the SOAP note is 80% drafted.

**HAI-DEF Model Stack**

| Model | Role | Why this model |
|---|---|---|
| **MedASR** (105M) | Medical speech-to-text | Recognizes clinical vocabulary (drug names, procedures, anatomy) that general ASR models garble. Runs on CPU, <2s latency per chunk. |
| **MedGemma-27b-text-it** | Clinical reasoning engine | The orchestrator brain: SOAP drafting, medication extraction, drug interaction checks, differential diagnosis, ICD-10/CPT coding, red-flag alerts, patient summaries. Strongest reasoning in the HAI-DEF suite. |
| **MedGemma-1.5-4b-it** | Medical vision | Analyzes X-rays, skin photos, and extracts structured lab values from report images. The 1.5 update's document understanding handles lab report tables. |
| **MedSigLIP-448** | Image retrieval | Embeds uploaded images for FAISS similarity search against a medical atlas, returning top-3 matching conditions for differential support. |
| **HeAR** | Audio biomarker analysis | Extracts health-related acoustic embeddings from patient audio segments. Drop-in ready for trained audio classifiers (cough detection, respiratory sounds) via the pluggable classifier registry. |

This is the complete HAI-DEF reference architecture Google designed: MedASR for speech, MedGemma for reasoning, MedGemma-1.5 for vision, MedSigLIP for retrieval, HeAR for audio biomarkers. Each model fills a role the others cannot perform.

**Two Operating Modes**

1. **In-Room (Real-Time Agent)** — The agent listens during the visit. Audio streams through a WebSocket, is transcribed by a dual-ASR pipeline (MedASR + Whisper with entity-guided merge), diarized by Pyannote, and fed to an orchestrator that autonomously calls 10+ specialized tools. The physician sees a live sidebar with alerts, medications, differential, and a continuously updating SOAP draft. No interaction required — just practice medicine.

2. **Post-Visit (Documentation Agent)** — The physician reviews the pre-populated SOAP note in an editable markdown-rendered view, triggers ICD-10/CPT code extraction, generates a plain-language patient summary (6th-grade reading level), and exports as PDF or clipboard text for EHR paste.

**Agentic Workflow (not a pipeline)**

Open Attend's orchestrator is a genuine agentic system. It receives each transcript chunk and *decides* what to do based on clinical content — not a fixed sequence:

| Trigger | Autonomous Action |
|---|---|
| Medication name detected | `extract_medications` → `check_interactions` |
| Allergy mentioned | Pin persistent alert, cross-reference new prescriptions |
| Red-flag symptoms (exertional chest pain, neuro deficits) | Surface urgent clinical alert |
| Mood/sleep/appetite signals | Prompt PHQ-2/GAD-2 screening |
| Order verbalized ("let's order a CBC") | Pre-fill order with CPT code + clinical indication |
| Exam findings spoken | Route to SOAP Objective section |
| New symptom identified | Update running differential diagnosis |
| Family history stated | Surface relevant screening guidelines |
| Every N chunks | Refresh SOAP draft sections |

The model decides which tools to invoke. The code dispatches. This is model-driven tool dispatch grounded in clinical context.

### Technical Details

**Architecture**

```
Browser (React + TypeScript + Tailwind)
    │
    ├── WebSocket ──────────► FastAPI Backend
    │   (raw PCM audio)            │
    │                              ├── AudioBuffer (15s batches, flush-at-silence)
    │                              │
    │                              ├── Parallel ASR Pipeline:
    │                              │   ├── MedASR (105M CTC, medical vocabulary)
    │                              │   ├── Whisper-base (conversational speech)
    │                              │   └── Pyannote 3.1 (speaker diarization)
    │                              │
    │                              ├── Entity-Guided Transcript Merge
    │                              │   MedASR entities → correct Whisper output
    │                              │
    │                              ├── Speaker Registry
    │                              │   Embedding-based tracking + LLM role assignment
    │                              │
    │                              ├── Orchestrator (throttled, independent cooldowns)
    │                              │   ├── SOAP note drafting (S/O/A/P sections)
    │                              │   ├── Medication extraction + interaction checks
    │                              │   ├── Clinical alerts (red flags, mental health)
    │                              │   ├── Differential diagnosis
    │                              │   ├── Order pre-fill with CPT codes
    │                              │   └── HeAR audio biomarker analysis
    │                              │
    │                              └── Vision Pipeline
    │                                  ├── MedGemma-1.5-4b-it (image + lab analysis)
    │                                  └── MedSigLIP + FAISS (similar case retrieval)
    │
    ├── REST polling ──────► GET /session/{id} (full session state)
    └── Static serving ────► Built Vite SPA
```

**Key Design Decisions**

1. **Dual-ASR + entity-guided merge** — MedASR excels at clinical vocabulary but garbles conversational speech ("Hi Doctor Chen" → "doctorch"). Whisper handles conversation but misses medical terms. An LLM merge fuses both, preferring MedASR for clinical entities and Whisper for everything else. Result: best-of-both transcription.

2. **Buffer-and-batch, not per-utterance** — Audio accumulates server-side for 15 seconds (5s for the first batch). CTC models need longer context. Diarization is unreliable on <4s clips. A silence-detection flush prevents splitting mid-word across batches.

3. **Throttled orchestrator with independent cooldowns** — SOAP, medications, and alerts don't re-run on every batch. Each tool has an independent cooldown (30–60s) to avoid redundant LLM calls while keeping the sidebar responsive.

4. **Speaker registry with persistent embeddings** — Pyannote embeddings are matched against a cosine-similarity registry. Speakers get consistent IDs across batches. Role assignment (doctor/patient/nurse) runs via MedGemma once enough context exists, then merges duplicate IDs.

5. **Section-specific SOAP generation with anti-hallucination verification** — The eval path generates each SOAP section independently with strict grounding rules (never fabricate vitals, labs, or exam findings not explicitly stated), followed by a two-pass verification that checks every claim against the original transcript.

6. **Privacy-by-design** — Session data persists in encrypted SQLite (SQLCipher AES-256). Audio recordings are stored locally with a 7-day auto-delete TTL. No PHI is transmitted externally. Audio never leaves the server. All models are open-weight with zero external API dependencies for inference.

**Evaluation Results (ACI-Bench, 80 dialogues)**

| Metric | Score |
|---|---|
| ROUGE-1 | 0.517 |
| ROUGE-2 | 0.224 |
| ROUGE-L | 0.299 |
| Entity Precision | 48.5% |
| Entity Recall | 40.4% |
| **Entity F1** | **43.0%** |
| Entity Faithfulness | 65.9% |
| ICD-10 Code F1 | 58.2% |
| CPT Code F1 | 73.4% |

ICD-10 and CPT code extraction uses MedGemma-1.5-4b-it, which outperforms the 27B model on structured code extraction (ICD-10 F1: 58.2% vs 36.3%, CPT F1: 73.4% vs 70.0%). The smaller model produces more standard-format codes that pass validation against the CMS lookup table. All other clinical reasoning tasks (SOAP drafting, entity extraction, differential diagnosis) use MedGemma-27b-text-it.

**Transcription (Fareez OSCE, 25 audio files, 5 specialties, 15s chunked)**

| Model | WER | MEER |
|---|---|---|
| Whisper-base (baseline) | 0.219 | 0.600 |
| MedASR (standalone) | 0.426 | 0.599 |
| Entity-guided merge (MedGemma 27B) | 0.238 | 0.555 |

The entity-guided merge reduces the Medical Entity Error Rate (MEER) by 7.5% vs. Whisper alone — the merge correctly preserves drug names, diagnoses, and clinical terms that Whisper garbles. Audio is chunked into 15-second segments matching the production real-time pipeline.

**Deployment**

The entire stack — frontend, backend, all five models — runs on a single GPU instance (A100 or A6000, ~$0.80/hr on vast.ai). No cloud API required for inference. For production, the identical stack deploys inside a hospital VPC or on-premise server behind TLS, with the clinic device (tablet/laptop) connecting over the local network. MedASR (105M) runs on CPU; MedGemma-27b requires a single GPU.

**Feature Set**

- Real-time transcription with speaker diarization and role assignment
- Live SOAP note drafting with markdown rendering (updated as conversation unfolds)
- Real-time Clinical Decision Support (see below)
- Medical image analysis (X-rays, skin photos) with similar-case retrieval
- Lab report image extraction with structured value parsing and abnormal flagging
- HeAR audio biomarker analysis with waveform visualization and drop-in classifier registry
- Pluggable classifier architecture — drop-in ready for any trained image or audio classifier (TorchXRayVision, respiratory sound CNNs, skin lesion classifiers, etc.)
- ICD-10 and CPT code extraction with confidence scores
- Patient summary generation at 6th-grade reading level
- PDF export, clipboard copy for EHR paste
- Editable post-visit SOAP editor with format toolbar (bold, italic, bullets)

**Clinical Decision Support**

The real-time alerting and reasoning layer that separates Open Attend from every competitor. No ambient AI scribe on the market offers CDS during the encounter — they all generate notes after the visit. Open Attend's orchestrator continuously analyzes the conversation and autonomously triggers decision support tools as clinical content is detected:

| CDS Capability | Trigger | Output |
|---|---|---|
| **Drug interaction checks** | Medication name detected (2+ meds in session) | Severity, mechanism, and recommendation alerts |
| **Red-flag symptom alerts** | Exertional chest pain, neurological deficits, acute abdomen, etc. | Urgent clinical alert with suggested workup |
| **Differential diagnosis** | New symptom identified | Running ranked differential (3–7 diagnoses), refines with each chunk |
| **Mental health screening prompts** | Mood, sleep, or appetite signals detected | PHQ-2/GAD-2 screening prompt surfaced to physician |
| **Lab value flagging** | Lab results uploaded or mentioned | Abnormal values highlighted with clinical context (e.g., elevated creatinine + NSAID → caution) |
| **Family history → screening guidelines** | Family history stated | Relevant USPSTF screening guidelines surfaced |
| **Order pre-fill with CPT codes** | Verbal orders detected | Structured pending orders with CPT codes pre-populated |

Each tool runs on independent Fibonacci-increasing throttle intervals (30–60s) to avoid alert fatigue while staying responsive to new clinical signals. All CDS outputs appear in the physician's sidebar in real time — no clicks, no prompts, no workflow interruption.

**Data Handling & HIPAA Compliance**

Open Attend is built on a privacy-by-design architecture: all models run locally on the clinic's hardware, no patient data is transmitted to external APIs for inference, and there is no cloud storage dependency. The entire inference stack (MedASR, MedGemma, MedSigLIP, HeAR) executes on-premise, ensuring PHI never leaves the facility's network boundary.

| Data Type | Storage | Encryption | Retention | Access |
|---|---|---|---|---|
| Audio recordings | Local filesystem (~/.openattend/audio/) | AES-256 at rest | 7-day auto-delete | Session owner only |
| Session notes (SOAP, meds, alerts) | SQLite (~/.openattend/sessions.db) | SQLCipher AES-256 page encryption | Persistent until manual delete | Local only, no cloud |
| Uploaded images | In-memory only | N/A (RAM) | Session lifetime | Session owner only |
| PHI/PII | Never transmitted externally | All inference local | No cloud API calls | On-premise only |

**Competitive Landscape**

The ambient AI scribe market ($5.3B Abridge valuation, June 2025) is consolidating around cloud-only, proprietary, documentation-only products. Open Attend occupies a fundamentally different position.

| Feature | DAX Copilot ($369/mo) | Abridge (~$200/mo) | Suki ($299–399/mo) | Freed ($99/mo) | **Open Attend (open)** |
|---|---|---|---|---|---|
| Real-time mid-visit note | Partial | No (post-visit) | Yes | No | **Yes** |
| Drug interaction detection | No | No | No | No | **Yes** |
| Red-flag clinical alerts | No | No | No | No | **Yes** |
| Mental health screening | No | No | No | No | **Yes (PHQ-2/GAD-2)** |
| Live differential diagnosis | No | No | No | No | **Yes** |
| Medical image analysis | No | No | No | No | **Yes (MedSigLIP + FAISS)** |
| Lab image parsing + alerts | No | No | No | No | **Yes** |
| Audio biomarker analysis | No | No | No | No | **Yes (HeAR)** |
| ICD-10/CPT coding | Via Epic | Yes | Yes | Basic | **Yes** |
| Order pre-fill | Epic only | Epic only | Yes | No | **Yes** |
| Open-weight models | No | No | No | No | **Yes (all 5)** |
| On-premise deployment | No | No | No | No | **Yes** |
| EHR integration | Epic (deep) | Epic (deep) | Epic, Cerner, athena | Copy-paste | **FHIR R4 (direct)** |

**Key differentiators:**

1. **Clinical decision support during the visit** — No competitor offers drug interaction detection, red-flag alerting, or live differential diagnosis. Open Attend's CDS layer represents a category expansion, not a feature increment.
2. **Multimodal medical intelligence with pluggable classifiers** — Medical image analysis (X-ray, skin, labs), audio biomarker detection (HeAR), and a drop-in classifier registry for trained diagnostic models don't exist in any ambient scribe product. Any trained classifier — chest X-ray pathology, respiratory sound CNN, skin lesion detector — can be plugged into the registry and run automatically during analysis, with the LLM interpreting structured predictions in clinical context. The closest analogues are standalone radiology AI tools (Viz.ai, Aidoc) that are entirely separate products.
3. **Open-weight, on-premise, data sovereign** — Every competitor is cloud-only and proprietary. This is structurally incompatible with FQHCs, VA/DoD (FedRAMP), international markets (EU GDPR), and resource-constrained settings.
4. **Cost** — At $99–667/month per physician for competitors, Open Attend's self-hosted model targets zero marginal cost per provider at scale. GPU infrastructure amortizes across all providers at a facility.

**EHR Integration Path**

Open Attend supports FHIR R4 for bidirectional EHR integration:

- **Pre-visit import** — Pull `Patient`, `MedicationRequest`, `AllergyIntolerance`, `Condition`, and `Observation` resources to pre-populate the clinical context before the visit begins. The orchestrator starts with the patient's medication list, allergies, and problem list already loaded.
- **Post-visit export** — POST a `DocumentReference` (LOINC `11506-3`: Progress Note) with the finalized SOAP note as structured text or PDF. ICD-10 codes map to `Condition` resources, orders to `ServiceRequest`.
- **Auth model** — SMART on FHIR (OAuth 2.0) for production EHR launches. The physician clicks a button inside Epic/Cerner, Open Attend opens in-context with patient identity pre-resolved.
- **Testing** — Validated against SMART on FHIR Sandbox (launch.smarthealthit.org) and Cerner Open Sandbox with Synthea-generated synthetic patients.

**Recommended Deployment & Cost Estimate**

All five HAI-DEF models are available in Google Cloud's Vertex AI Model Garden with one-click deployment via pre-built vLLM containers. Google Cloud is HIPAA-eligible with a signed BAA covering Vertex AI, GCE, GKE, and Cloud Run.

*Small Clinic (5 physicians, 100 visits/day, 8 hrs/day):*

| Component | Infrastructure | Monthly Cost |
|---|---|---|
| MedGemma-27b (reasoning) | GCE A100 80GB, 1-yr commit, clinic hours | ~$580 |
| MedGemma-4b + MedSigLIP + HeAR + MedASR | Cloud Run with L4 GPU, scale-to-zero | ~$150 |
| Storage, networking, logging | Cloud Storage + Cloud Logging | ~$50 |
| **Total** | | **~$780/month** |
| **Per physician** | | **~$156/month** |

vs. Nuance DAX at $369/mo, Abridge at $200/mo, Suki at $299–399/mo — with more clinical features than any of them.

*Hospital Scale (50 physicians, 1,000 visits/day):*

| Component | Infrastructure | Monthly Cost |
|---|---|---|
| MedGemma-27b (reasoning) | Vertex AI dedicated endpoint, 2× A100 80GB | ~$9,000 |
| MedGemma-4b + auxiliary models | GKE GPU node pool (L4), autoscaled | ~$800 |
| Storage, networking, monitoring | Cloud infrastructure | ~$200 |
| **Total** | | **~$10,000/month** |
| **Per physician** | | **~$200/month** |

At hospital scale, Vertex AI dedicated endpoints become cost-effective (near-continuous utilization). Per-physician cost drops below every commercial competitor while delivering clinical decision support none of them offer.

*Development & Evaluation (current setup):*

| Component | Infrastructure | Monthly Cost |
|---|---|---|
| Full stack (all 5 models) | vast.ai A100 80GB spot | ~$150 |

vast.ai is not HIPAA-eligible (no BAA) and is used exclusively for development and evaluation with de-identified data.

**Limitations**

- Models used as-is — quality depends on prompt engineering, not fine-tuning
- Speaker diarization is best-effort (no dedicated diarization training)
- EHR integration via FHIR R4 is architecturally complete but not yet deployed in a production EHR environment
- English-only
- Entity recall (40.4%) reflects conservative grounding — the model says "Not documented" rather than inferring unstated information, prioritizing faithfulness (65.9%) over completeness
- Web application only (optimized for tablet/desktop)

**Links**

- **Source Code:** [GitHub repository]
- **Live Demo:** [Deployed application URL]
- **Demo Video:** [3-minute walkthrough]
