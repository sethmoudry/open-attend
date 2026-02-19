# Scribe — AI Clinical Documentation Agent

**Google HAI-DEF Competition | Main Track + Agentic Workflow Prize**

---

## Team

[Team Name]
[Member names and affiliations]

---

## Problem Statement

Clinical documentation is broken. For every 1 hour spent with patients, physicians spend 2 hours on paperwork (Sinsky et al., *Annals of Internal Medicine*, 2016). Documentation is the single largest driver of physician burnout, contributing to a crisis where 63% of physicians report burnout symptoms (Medscape, 2023). The downstream cost is staggering: an estimated $4.6 billion annually in physician turnover alone.

Human medical scribes partially address this, but at $36,000-$50,000/year per scribe they don't scale, and they introduce their own variability and training overhead. Existing AI documentation tools operate post-visit only -- the physician still carries the cognitive burden of remembering clinical details after the encounter ends.

**The gap:** No solution provides real-time clinical intelligence during the encounter itself. Documentation should happen while the visit is happening, not after.

---

## Solution

Scribe is a real-time in-room documentation agent that listens to doctor-patient conversations, reasons about clinical content as it hears it, and continuously builds structured documentation. By the time the visit ends, the SOAP note is 80% complete.

**Two operating modes:**

1. **In-Room (Real-Time)** -- The agent listens during the visit, transcribes speech, extracts medications, flags drug interactions, detects red-flag symptoms, builds a running differential diagnosis, and drafts the SOAP note live. The physician glances at a sidebar; no interaction required.

2. **Post-Visit (Review & Export)** -- The physician reviews the pre-populated SOAP note, edits as needed, triggers ICD-10/CPT code extraction, generates a patient summary at a 6th-grade reading level, and exports everything as PDF or clipboard text for EHR paste.

---

## Technical Architecture

### HAI-DEF Models

| Model | Role | Size | Why It's Necessary |
|---|---|---|---|
| **MedASR** | Medical speech-to-text | 105M | 58-82% fewer errors than general ASR on clinical speech. Runs on CPU. |
| **MedGemma-27b-text-it** | Clinical reasoning engine | 27B | Orchestrator brain: SOAP drafting, med extraction, interaction checks, differential building, code extraction, patient summaries. |
| **MedGemma-4b-it** | Medical image analysis | 4B | Analyzes X-rays, skin photos, lab reports uploaded during or after the visit. |
| **MedSigLIP-448** | Image retrieval | - | Embeds images for FAISS similarity search against a medical atlas, returning top-3 matching conditions. |

This is the complete HAI-DEF reference architecture: MedASR feeds transcripts to MedGemma for reasoning, MedGemma-4b handles imaging, and MedSigLIP handles retrieval. Each model fills a role the others cannot perform.

### System Design

```
Audio Stream --> MedASR (CPU) --> Transcript Chunks
                                       |
                                  Orchestrator (stateful agent loop)
                                       |
                    +------------------+------------------+
                    |                  |                  |
              Extract structured   Update SOAP       Dispatch tools
              data from chunk      draft live         autonomously
                    |                  |                  |
           +-------+-------+          |          +-------+-------+
           |       |       |          |          |       |       |
         Meds   Allergies  Sx       S/O/A/P   Interactions  Differential
           |                                     |
           v                                     v
     check_interactions                   Sidebar alerts
```

- **WebSocket streaming** delivers transcript chunks to the frontend in real-time
- **Context isolation**: each tool receives only the data it needs (e.g., `check_interactions` gets only the medication list, never the full transcript)
- **Session state** is ephemeral (RAM-only, 2-hour TTL, no PHI persisted)

---

## Agentic Workflow Design

Scribe is not a pipeline. It is a genuine agentic system. The distinction matters.

In a pipeline, every input follows the same path: transcribe, extract, summarize, done. In Scribe, the orchestrator receives each transcript chunk and **decides what to do based on clinical content**. If the patient mentions a medication, the orchestrator calls `extract_medications` then `check_interactions`. If the patient describes exertional chest pain, it flags a red-flag alert. If the doctor says "let's order a stress test," it pre-fills an order with CPT code and clinical indication. If none of these triggers are present, it simply updates the SOAP draft. The model decides; the code dispatches.

### 9 Autonomous Decision Points (In-Room)

| ID | Trigger | Action |
|----|---------|--------|
| D1 | Medication name detected | `extract_medications` then `check_interactions` |
| D2 | Allergy or adverse reaction mentioned | Extract and pin persistent alert |
| D3 | Family history stated | `check_screening_guidelines` |
| D4 | Red-flag symptoms (chest pain, neuro deficits) | Surface urgent clinical alert |
| D5 | Mood/sleep/appetite signals | Prompt PHQ-2/GAD-2 screening |
| D6 | Order or referral verbalized | Pre-fill order with CPT + indication |
| D7 | Exam findings spoken | Route to SOAP Objective section |
| D8 | New symptom identified | Update `build_differential` |
| D9 | Every N chunks | Refresh SOAP draft sections |

The orchestrator runs a continuous reasoning loop. It does not wait for human instruction. It does not follow a fixed sequence. This is model-driven tool dispatch grounded in clinical context -- the definition of agentic behavior.

---

## Key Features

- **Real-time transcription** with MedASR, speaker diarization (best-effort), and sub-2-second latency per chunk
- **Live SOAP drafting** that builds incrementally as the conversation unfolds
- **Drug interaction detection** triggered automatically when medications are mentioned
- **Red-flag alerts** for symptoms suggesting urgent/emergent conditions
- **Differential diagnosis** that refines as new symptoms accumulate
- **ICD-10/CPT code extraction** from finalized SOAP assessment and plan
- **Patient summary generation** written at a 6th-grade reading level
- **Medical image analysis** via MedGemma-4b with similar-case retrieval via MedSigLIP + FAISS
- **PDF export** and clipboard copy for EHR integration

---

## Impact

| Metric | Current State | With Scribe |
|--------|--------------|-------------|
| Documentation time per visit | ~16 min (Sinsky et al.) | Est. 3-5 min (review + approve) |
| Documentation after hours | 1-2 hrs/day | Near zero |
| Annual scribe cost | $36,000-$50,000/scribe | $0 (runs on existing infrastructure) |
| Note completion at visit end | 0% | ~80% (live draft) |
| Physician burnout driver #1 | Documentation | Addressed at the source |

Scribe targets the highest-leverage intervention point in physician burnout: eliminating documentation as a separate task from patient care. The visit *is* the documentation.

---

## Limitations & Future Work

**Current limitations:**
- Models used as-is with no fine-tuning -- quality depends on prompt engineering and HAI-DEF model capabilities
- Speaker diarization is best-effort (no dedicated diarization model)
- No direct EHR integration -- clipboard copy serves as a bridge
- English-only
- Web application only (optimized for tablet/desktop, not native mobile)

**Future directions:**
- Multi-language support for diverse patient populations
- Native mobile application with offline-capable MedASR
- EHR FHIR integration for direct note submission
- Fine-tuning MedGemma on institution-specific note styles
- Longitudinal patient context across visits

---

## Links

- **Source Code:** [GitHub repository URL]
- **Live Demo:** [Deployed application URL]
- **Demo Video:** [3-minute walkthrough URL]
