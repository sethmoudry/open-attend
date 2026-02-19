# Open Attend — 3-Minute Demo Script

**Format:** Screen recording with voiceover narration. Read the **NARRATION** lines. Stage directions in *italics*.

---

## 0:00–0:25 — The Problem (no screen needed, or title card)

**NARRATION:**

> For every hour a physician spends with patients, they spend two more on paperwork. Forty-nine percent of their workday goes to documentation. After clinic hours, another 86 minutes of "pajama time" finishing notes. The result: a 43 percent burnout rate and $4.6 billion in annual turnover.
>
> Every AI scribe on the market generates notes *after* the visit ends. None of them offer clinical decision support *during* the encounter.
>
> Open Attend does both.

---

## 0:25–0:45 — Landing + Visit Setup

*Show the landing page. Click "I Understand" on the disclaimer.*

**NARRATION:**

> This is Open Attend — a real-time clinical documentation agent built entirely on open-weight MedGemma models. Everything runs on a single GPU. No cloud APIs, no vendor lock-in, no data leaving your infrastructure.

*Click "Start Visit" from the dashboard. Show the Visit Setup page — enter patient name, select visit type.*

> The physician starts a new visit, selects the visit type, and hits record. From this point forward, the agent is listening.

*Click "Start Recording."*

---

## 0:45–1:45 — In-Room: Live Agent in Action

*Show the In-Room view. The transcript panel is on the right, SOAP note on the left, sidebar with alerts/meds/differential.*

*Play a sample clinical conversation (or narrate over a pre-recorded session). The transcript should be populating in real time with speaker labels (DR: / PT:).*

**NARRATION:**

> Audio streams through a WebSocket to the backend. Two ASR models run in parallel — MedASR for clinical vocabulary, Whisper for conversational speech — and an LLM merges the outputs, preferring MedASR's drug names and diagnoses. Pyannote handles speaker diarization so we know who said what.

*Point to the SOAP note updating on the left side.*

> Watch the SOAP note build itself in real time. Each section — Subjective, Objective, Assessment, Plan — updates as the conversation progresses. The physician doesn't type anything.

*Point to the sidebar — medications appearing, then an interaction alert popping up.*

> Here's where it gets interesting. The patient mentions they're on lisinopril and ibuprofen. The agent catches both, runs an interaction check, and flags it: NSAIDs can reduce the efficacy of ACE inhibitors and increase renal risk. This happens automatically — no click, no prompt.

*Point to differential diagnosis updating.*

> A differential diagnosis builds as new symptoms are mentioned. Red-flag alerts surface instantly if the agent detects anything urgent — exertional chest pain, neurological deficits, acute abdomen. It even prompts PHQ-2 screening when it picks up mood or sleep signals.

*Point to order pre-fill if visible.*

> When the doctor says "let's order a CBC and a metabolic panel," the agent pre-fills the orders with CPT codes. By the time the visit ends, the note is 80 percent done.

---

## 1:45–2:15 — Post-Visit: Review + Multimodal

*Click "End Visit" to transition to Post-Visit view. Show the editable SOAP editor.*

**NARRATION:**

> After the visit, the physician reviews the SOAP note in an editable view. They can refine any section — the editor supports markdown formatting with bold, italic, and bullet controls.

*Show the HeAR audio analysis section — waveform player and embedding results.*

> Open Attend isn't just text. HeAR analyzes audio biomarkers from the visit — extracting health acoustic embeddings from patient speech segments. The classifier registry is pluggable: drop in a trained cough detector or respiratory sound model and it runs automatically.

*Show the waveform visualization and any classifier output.*

> And it handles images too. Upload a chest X-ray and MedGemma's vision model analyzes it, while MedSigLIP finds similar cases from a medical atlas. Lab report photos get structured value extraction with abnormal flagging.

*Click "Generate Codes." Show ICD-10 and CPT codes appearing.*

> One click extracts ICD-10 and CPT codes with confidence scores. Another generates a plain-language patient summary at a sixth-grade reading level.

---

## 2:15–2:45 — Architecture + What Makes It Different

*Show the system architecture diagram (docs/diagrams/system_overview.png) or the architecture from the writeup.*

**NARRATION:**

> Under the hood: five HAI-DEF models working together. MedASR transcribes. MedGemma-27B reasons — it's the orchestrator brain that decides which tools to call based on what it hears. MedGemma-4B handles vision. MedSigLIP handles image retrieval. HeAR analyzes audio biomarkers. The classifier registry is pluggable — drop in any trained chest X-ray or respiratory sound model and it runs automatically.
>
> The orchestrator is a genuine agentic system. It doesn't follow a fixed pipeline — it reasons about each transcript chunk and autonomously dispatches to ten specialized tools with independent throttle intervals.

---

## 2:45–3:00 — Closing

*Return to the dashboard showing the completed session, or show the competitive comparison table.*

**NARRATION:**

> No ambient AI scribe offers drug interaction detection, red-flag alerting, live differential diagnosis, or medical image analysis during the visit. They generate notes. Open Attend generates clinical intelligence.
>
> It's fully open-weight, deploys on-premise, and costs a fraction of any commercial alternative. This is what MedGemma was built for.

---

## Timing Guide

| Section | Duration | Cumulative |
|---------|----------|------------|
| The Problem | 25s | 0:25 |
| Landing + Setup | 20s | 0:45 |
| In-Room Live Agent | 60s | 1:45 |
| Post-Visit + Multimodal | 30s | 2:15 |
| Architecture | 30s | 2:45 |
| Closing | 15s | 3:00 |

## Recording Tips

- Record at 1920×1080, 30fps
- Use a clean browser window (no bookmarks bar, no other tabs)
- Pre-load a sample conversation so the demo flows without waiting for real transcription
- Record narration separately and overlay (cleaner audio)
- Keep mouse movements deliberate and slow — viewers need to track what you're pointing at
