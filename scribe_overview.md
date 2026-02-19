# Scribe

**AI clinical documentation agent built with HAI-DEF**

An in-room and post-visit clinical documentation agent that listens to doctor-patient conversations, builds structured notes in real-time, surfaces clinical intelligence as it hears it, and finalizes exportable documentation after the visit ends.

---

## Competition Track

**Main Track** + **Agentic Workflow Prize**

Agentic angle: a real-time orchestrator continuously processes streaming transcript chunks, reasons about clinical context, and autonomously calls specialized tools (interaction checks, screening guidelines, differential building, code extraction) without waiting for human instruction. This is genuine agentic behavior — the model decides what to do based on what it hears.

---

## Models Used

- **MedASR** (105M) — Medical speech-to-text, transcribes doctor-patient conversation with 58–82% fewer errors than general ASR models. Runs on CPU.
- **MedGemma-27b-text-it** — The reasoning brain. Processes transcript chunks, builds SOAP notes, extracts codes, checks interactions, surfaces clinical alerts. Text-only, strongest reasoning.
- **MedGemma-1.5-4b-it** — The eyes. Analyzes uploaded medical images (X-rays, skin photos) and extracts structured lab values from report photos. Multimodal with document understanding.
- **MedSigLIP-448** — Embedding-based image retrieval. Finds similar cases from a reference atlas for differential support.

> **Why four models?** This is the exact pipeline Google designed and diagrammed in their HAI-DEF documentation: MedASR feeds transcripts to MedGemma, which generates SOAP notes. MedGemma-1.5-4b-it handles imaging and lab report extraction (leveraging the 1.5 update's document understanding). MedSigLIP handles retrieval. Each model fills a role the others literally cannot perform.

---

## Two Modes

### Mode 1: In-Room (Real-Time Agent)
The doctor is with the patient. The agent listens and works in the background, surfacing useful information without interrupting the visit. By the time the visit ends, the SOAP note is 80% drafted.

### Mode 2: Post-Visit (Documentation Agent)
The doctor ends the visit. The agent finalizes the SOAP note, the doctor reviews and edits, imaging is analyzed, codes are extracted, and everything is exported.

---

## Application Flow

### Step 1 — Landing Page
   a. Clean landing with "Scribe" branding and two CTAs: "Start Visit" and "Resume Post-Visit Review"
   b. Brief explainer: what it does, what it doesn't do, not-a-diagnostic-tool disclaimer
   c. Mobile-responsive but optimized for tablet/desktop (this is a doctor's tool)
   d. Disclaimer acknowledgment required before proceeding

### Step 2 — Visit Setup
   a. Doctor enters minimal context: patient name/ID (optional), visit type (follow-up, new patient, urgent), chief complaint if known
   b. Microphone permission request with clear explanation
   c. Audio input selector (built-in mic, external mic, headset)
   d. "Start Recording" button — large, obvious, unmissable
   e. Session created, Mode 1 begins

### Step 3 — In-Room: Live Transcription
   a. Audio captured from browser microphone (MediaRecorder API or Web Audio API)
   b. Audio chunks streamed to backend at regular intervals (e.g., every 5 seconds)
   c. MedASR processes each chunk → returns transcript segment with timestamps
   d. Transcript displayed in left panel, scrolling, with speaker diarization if possible (DR: / PT:)
   e. Transcript segments accumulate in session state
   f. Visual indicator: recording active (pulsing red dot), audio level meter
   g. Pause/resume button for breaks (bathroom, phone call)

### Step 4 — In-Room: Real-Time Agent Processing
   a. Each new transcript chunk sent to orchestrator
   b. Orchestrator calls `process_chunk(chunk, accumulated_context)` → MedGemma-27b-text-it
   c. Agent reasons about the chunk and decides which tools to invoke:

   **4d. Medication Extraction**
   - Trigger: patient or doctor mentions a medication name
   - `extract_medications(chunk)` → structured list: drug name, dose, frequency
   - Medications surfaced immediately in sidebar under "Medications" section
   - Running medication list maintained in session

   **4e. Interaction Check**
   - Trigger: new medication detected (either current or newly prescribed)
   - `check_interactions(medication_list)` → MedGemma-27b-text-it
   - Flags surfaced as alerts in sidebar: severity, mechanism, recommendation
   - No-interaction confirmations shown as green checkmarks

   **4f. Allergy Flagging**
   - Trigger: patient mentions allergy or adverse reaction
   - Extracted and pinned to top of sidebar as persistent alert
   - Cross-referenced against any newly prescribed medications

   **4g. Family History / Screening Guidelines**
   - Trigger: patient mentions family history of a condition
   - `check_screening_guidelines(condition, patient_age)` → MedGemma-27b-text-it
   - Relevant screening recommendations surfaced in sidebar

   **4h. Red Flag Detection**
   - Trigger: symptoms suggesting urgent/emergent conditions (exertional chest pain, sudden severe headache, neurological deficits)
   - Alert surfaced prominently in sidebar: "Consider cardiac workup" / "Rule out stroke"
   - Not intrusive — doctor decides what to act on

   **4i. Mental Health Signal Detection**
   - Trigger: patient mentions mood, sleep, appetite, hopelessness, stress
   - Sidebar suggestion: "Consider PHQ-2/GAD-2 screening"
   - If doctor administers screening verbally, agent scores responses from transcript

   **4j. Background Differential Building**
   - As symptoms accumulate, agent builds a running differential diagnosis
   - Updated silently in sidebar under "Working Differential"
   - New transcript data refines or re-ranks differentials

   **4k. Live SOAP Draft**
   - Agent continuously drafts SOAP note sections from accumulated transcript:
     - **S (Subjective):** patient-reported symptoms, history, medications, allergies, social/family history
     - **O (Objective):** exam findings mentioned by doctor, vitals if stated
     - **A (Assessment):** working differential, primary diagnosis direction
     - **P (Plan):** any mentioned orders, prescriptions, referrals, follow-up
   - Draft visible in sidebar under "Draft SOAP" — updates in near-real-time
   - Doctor can glance at it but doesn't need to interact during the visit

   **4l. Order Pre-Fill**
   - Trigger: doctor says "let's order a CBC" or "I'm going to refer you to cardiology"
   - Agent pre-populates: test name, CPT code, clinical indication (pulled from conversation context)
   - Surfaced in sidebar under "Pending Orders"

### Step 5 — In-Room: Image Upload (Optional)
   a. Doctor taps "Upload Image" in sidebar without stopping recording
   b. Accepts photo from device camera or file upload (X-ray, skin photo, lab report, pathology)
   c. MedGemma-4b-it analyzes image → clinical description
   d. MedSigLIP embeds image → FAISS returns top-3 similar cases from atlas
   e. Results appear in sidebar: clinical description + similar condition matches
   f. Findings automatically inserted into Objective section of SOAP draft
   g. Recording continues uninterrupted throughout

### Step 6 — End Visit
   a. Doctor presses "End Visit" button
   b. Final audio chunk processed
   c. Confirmation: "Visit ended. Proceed to review?"
   d. Mode transitions from In-Room → Post-Visit
   e. Agent runs final pass: completes any partial SOAP sections, assembles full draft

### Step 7 — Post-Visit: SOAP Review & Edit
   a. Full-screen SOAP note editor with all four sections pre-populated from live draft
   b. Each section editable — doctor can modify, add, delete
   c. If doctor edits Assessment → agent re-evaluates: "Should Plan change based on updated Assessment?"
   d. Sidebar shows: full transcript (scrollable, searchable), all extracted data
   e. Doctor can highlight transcript sections and "pin" them to specific SOAP sections
   f. Track changes view available (what agent wrote vs. what doctor changed)

### Step 8 — Post-Visit: Image Analysis (if not done in-room)
   a. Doctor uploads imaging referenced during visit but not uploaded live
   b. Same pipeline as Step 5: MedGemma-4b-it + MedSigLIP
   c. Agent suggests where findings should be inserted in SOAP note
   d. Doctor approves or modifies placement

### Step 9 — Post-Visit: Code Extraction
   a. `extract_icd10_codes(assessment)` → MedGemma-27b-text-it
   b. Returns suggested ICD-10 codes with descriptions and confidence
   c. Displayed as selectable list — doctor confirms or removes
   d. `extract_cpt_codes(plan, orders)` → MedGemma-27b-text-it
   e. CPT codes for procedures and orders pre-populated
   f. Codes linked to relevant SOAP sections for audit trail

### Step 10 — Post-Visit: Medication Summary
   a. Full medication list: current (from patient report) + new (prescribed during visit)
   b. Interaction check results displayed alongside
   c. Allergy cross-reference confirmed
   d. Dosage, frequency, and instructions extracted from transcript

### Step 11 — Post-Visit: Follow-Up Plan
   a. `extract_followups(transcript, plan)` → MedGemma-27b-text-it
   b. Returns: follow-up timeline, pending orders, referrals, return visit recommendations
   c. Displayed as checklist — doctor confirms or modifies

### Step 12 — Post-Visit: Patient Summary
   a. `generate_patient_summary(soap, medications, followups)` → MedGemma-27b-text-it
   b. Plain-language summary of the visit for the patient
   c. Written at 6th-grade reading level
   d. Includes: what was discussed, any new medications (with instructions), follow-up steps, when to seek urgent care
   e. Doctor reviews before export

### Step 13 — Approve & Export
   a. Doctor reviews everything on a summary screen:
      - SOAP note (finalized)
      - ICD-10 / CPT codes
      - Medication list with interactions
      - Follow-up plan
      - Patient summary
   b. "Approve" button locks the note
   c. Export options:
      - Download SOAP as PDF
      - Download patient summary as PDF
      - Copy SOAP to clipboard (for EHR paste)
      - QR code linking to read-only session summary (time-limited)
   d. Session data cleared after export (no persistence)

### Step 14 — End State
   a. Confirmation: "Documentation complete. Session cleared."
   b. Option to start a new visit
   c. Feedback prompt for judges

---

## UI Layout

### In-Room Screen (Mode 1)
```
┌─────────────────────────────────────────────────────────────────────┐
│  Scribe                              🔴 Recording  ⏸ Pause  ⏹ End │
├────────────────────────────┬────────────────────────────────────────┤
│                            │                                        │
│   LIVE TRANSCRIPT          │   AGENT SIDEBAR                        │
│                            │                                        │
│   [14:32] DR: What brings  │   ⚠️ ALERTS                           │
│   you in today?            │   🔴 Allergy: Penicillin               │
│                            │                                        │
│   [14:32] PT: I've been    │   💊 MEDICATIONS                       │
│   having chest pain going  │   • Metformin 500mg BID                │
│   up stairs for about two  │   • Lisinopril 10mg daily              │
│   weeks now.               │   ✅ No interactions                    │
│                            │                                        │
│   [14:33] DR: Any other    │   🔍 WORKING DIFFERENTIAL              │
│   symptoms? Shortness of   │   1. Stable angina                     │
│   breath?                  │   2. Musculoskeletal                    │
│                            │   3. GERD                              │
│   [14:33] PT: Yeah,        │                                        │
│   sometimes when I walk    │   📋 DRAFT SOAP                        │
│   a lot. And I've been     │   S: 58yo M c/o exertional CP x2wk    │
│   really stressed at work  │      w/ assoc DOE. PMHx: DM2, HTN...  │
│                            │   O: [awaiting exam findings]          │
│   [14:34] DR: Are you on   │   A: Exertional CP, r/o ACS vs        │
│   any medications?         │      stable angina vs MSK...           │
│                            │   P: [updating...]                     │
│   [14:34] PT: Metformin    │                                        │
│   and lisinopril           │   📎 PENDING ORDERS                    │
│                            │   (none yet)                           │
│                            │                                        │
│   [auto-scrolling]         │   🖼 UPLOAD IMAGE                      │
│                            │                                        │
├────────────────────────────┴────────────────────────────────────────┤
│  Audio Level: ▓▓▓▓▓▓░░░░  │  Chunks processed: 14  │  Elapsed: 4m │
└─────────────────────────────────────────────────────────────────────┘
```

### Post-Visit Screen (Mode 2)
```
┌─────────────────────────────────────────────────────────────────────┐
│  Scribe — Post-Visit Review                       [Approve & Export]│
├────────────────────────────┬────────────────────────────────────────┤
│                            │                                        │
│   SOAP NOTE [editable]     │   TOOLS & OUTPUTS                      │
│                            │                                        │
│   ┌─ SUBJECTIVE ─────────┐│   🏷 ICD-10 CODES                      │
│   │ 58-year-old male      ││   ☑ I20.8 - Other angina pectoris     │
│   │ presenting with       ││   ☑ E11.9 - Type 2 DM                 │
│   │ exertional chest pain ││   ☑ I10 - Essential HTN                │
│   │ for two weeks...      ││   ☐ F41.9 - Anxiety (suggested)       │
│   └───────────────────────┘│                                        │
│                            │   💊 MEDICATIONS                       │
│   ┌─ OBJECTIVE ──────────┐│   Current:                              │
│   │ Vitals: ...           ││   • Metformin 500mg BID                │
│   │ CV: ...               ││   • Lisinopril 10mg daily              │
│   │ Imaging: [if any]     ││   New:                                 │
│   └───────────────────────┘│   • Aspirin 81mg daily                 │
│                            │   ✅ No interactions                    │
│   ┌─ ASSESSMENT ─────────┐│                                        │
│   │ 1. Exertional angina  ││   📅 FOLLOW-UPS                       │
│   │ 2. Type 2 DM, stable ││   • Stress test within 1 week          │
│   │ 3. HTN, controlled    ││   • Cardiology referral                │
│   └───────────────────────┘│   • Return visit 2 weeks               │
│                            │                                        │
│   ┌─ PLAN ───────────────┐│   🖼 IMAGE ANALYSIS                    │
│   │ - Order stress test   ││   (no images uploaded)                  │
│   │ - Refer cardiology    ││   [Upload Image]                       │
│   │ - Start ASA 81mg      ││                                        │
│   │ - RTC 2 weeks         ││   📄 PATIENT SUMMARY                  │
│   └───────────────────────┘│   [Generate] [Preview]                 │
│                            │                                        │
│   📝 FULL TRANSCRIPT       │                                        │
│   [expandable/searchable]  │                                        │
│                            │                                        │
├────────────────────────────┴────────────────────────────────────────┤
│  [Download SOAP PDF]  [Download Patient Summary]  [Copy to EHR]     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Architecture: Orchestrator + Tools

### Design Principle
The transcript is the source of truth. Each chunk is processed once by the orchestrator, which decides what tools to call based on clinical reasoning. Tools receive only the data they need — never the full transcript. The SOAP note is built incrementally, not generated from scratch at the end.

### Orchestrator
A stateful agent loop that receives transcript chunks in near-real-time, maintains a running clinical context object, and autonomously decides which tools to invoke. In Mode 1, it runs continuously. In Mode 2, it runs on-demand when the doctor triggers actions.

### Tools

| Tool | Model | Input (context boundary) | Output |
|---|---|---|---|
| `transcribe(audio_chunk)` | MedASR | Raw audio bytes | Transcript segment with timestamps |
| `process_chunk(chunk, context)` | MedGemma-27b-text-it | Latest chunk + running clinical context summary | Tool invocation decisions + SOAP updates |
| `extract_medications(chunk)` | MedGemma-27b-text-it | Transcript chunk only | Structured medication list |
| `check_interactions(medications)` | MedGemma-27b-text-it | Medication list only | Interaction flags with severity |
| `check_screening_guidelines(condition, age)` | MedGemma-27b-text-it | Condition + patient age | Screening recommendations |
| `build_differential(symptoms, history)` | MedGemma-27b-text-it | Structured symptom + history data | Ranked differential |
| `draft_soap_section(section, data)` | MedGemma-27b-text-it | Section name + relevant extracted data | SOAP section text |
| `analyze_image(image, context)` | MedGemma-4b-it | Image bytes + clinical context | Clinical description |
| `search_similar(image)` | MedSigLIP + FAISS | Image bytes only | Top-3 similar cases |
| `extract_icd10_codes(assessment)` | MedGemma-27b-text-it | Assessment text only | ICD-10 codes with confidence |
| `extract_cpt_codes(plan)` | MedGemma-27b-text-it | Plan text only | CPT codes |
| `generate_patient_summary(soap, meds, followups)` | MedGemma-27b-text-it | Structured data only | Plain-language patient summary |

### Context Isolation
```
Audio stream → MedASR → transcript chunks
                              │
                         orchestrator
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
           extract structured      update SOAP draft
           data from chunk         from new data
                    │                    │
        ┌───────────┼────────────┐       │
        ▼           ▼            ▼       ▼
   medications   allergies   symptoms   SOAP sections
        │                        │
        ▼                        ▼
   check_interactions    build_differential
        │                        │
        ▼                        ▼
   sidebar alerts         sidebar updates

Post-visit:
   SOAP draft → doctor edits → extract_codes → generate_patient_summary → export
   uploaded images → analyze_image + search_similar → insert into SOAP
```

### Decision Points (Orchestrator Logic)

**In-Room (continuous):**
- D1: Does chunk contain medication names? → `extract_medications` → `check_interactions`
- D2: Does chunk contain allergy mention? → extract and pin alert
- D3: Does chunk contain family history? → `check_screening_guidelines`
- D4: Does chunk contain red flag symptoms? → surface urgent alert
- D5: Does chunk contain mood/sleep/appetite signals? → surface PHQ screening prompt
- D6: Does chunk contain an order or referral? → pre-fill order with CPT + indication
- D7: Does chunk contain exam findings? → route to Objective section
- D8: Does chunk contain new symptoms? → update `build_differential`
- D9: Every N chunks → refresh SOAP draft sections

**Post-Visit:**
- D10: Doctor edits Assessment → prompt: "Update Plan to match?"
- D11: Image uploaded → analyze + suggest SOAP placement
- D12: All sections approved → unlock export options

---

## Data Objects

### TranscriptChunk
```json
{
  "id": "uuid",
  "timestamp_start": "float (seconds from visit start)",
  "timestamp_end": "float",
  "speaker": "doctor | patient | unknown",
  "text": "string",
  "processed": "bool"
}
```

### Medication
```json
{
  "name": "string",
  "dose": "string | null",
  "frequency": "string | null",
  "source": "patient_reported | prescribed",
  "chunk_id": "uuid"
}
```

### InteractionFlag
```json
{
  "drug_a": "string",
  "drug_b": "string",
  "severity": "high | moderate | low | none",
  "mechanism": "string",
  "recommendation": "string"
}
```

### ClinicalAlert
```json
{
  "type": "allergy | red_flag | screening_prompt | guideline",
  "message": "string",
  "source_chunk_id": "uuid",
  "priority": "urgent | info",
  "timestamp": "datetime"
}
```

### SOAPNote
```json
{
  "subjective": "string",
  "objective": "string",
  "assessment": "string",
  "plan": "string",
  "status": "drafting | review | approved",
  "last_updated": "datetime"
}
```

### DiagnosisCode
```json
{
  "code": "string",
  "description": "string",
  "confidence": "float",
  "source_section": "assessment | plan",
  "confirmed": "bool"
}
```

### ImageAnalysis
```json
{
  "id": "uuid",
  "image_url": "string",
  "clinical_description": "string",
  "similar_conditions": [
    {
      "condition_label": "string",
      "similarity_score": "float",
      "reference_image_url": "string"
    }
  ],
  "soap_section": "objective | null"
}
```

### FollowUpItem
```json
{
  "action": "string",
  "type": "lab | referral | imaging | return_visit | prescription",
  "timeframe": "string",
  "details": "string"
}
```

### PatientSummary
```json
{
  "visit_summary": "string",
  "new_medications": ["string"],
  "follow_up_steps": ["string"],
  "when_to_seek_care": "string",
  "reading_level": "6th grade"
}
```

### Session
```json
{
  "id": "uuid",
  "created_at": "datetime",
  "mode": "in_room | post_visit",
  "visit_type": "string",
  "patient_context": {
    "name": "string | null",
    "age": "int | null",
    "chief_complaint": "string | null"
  },
  "transcript_chunks": ["TranscriptChunk"],
  "medications": ["Medication"],
  "interaction_flags": ["InteractionFlag"],
  "clinical_alerts": ["ClinicalAlert"],
  "soap_note": "SOAPNote",
  "differential": ["string"],
  "image_analyses": ["ImageAnalysis"],
  "diagnosis_codes": ["DiagnosisCode"],
  "follow_ups": ["FollowUpItem"],
  "patient_summary": "PatientSummary | null",
  "pending_orders": [{"name": "string", "cpt_code": "string", "indication": "string"}]
}
```

---

## Database Schema

No persistent DB. All state lives in-memory per session. Sessions expire after 2 hours.

### FAISS Index (prebuilt)
```
Source:        Medical imaging atlas (ISIC, CheXpert subset, etc.)
Encoder:       MedSigLIP-448
Dimensions:    768
Metadata:      atlas_metadata.json
```

### File Storage (ephemeral)
```
/tmp/uploads/{session_id}/    → uploaded images
/tmp/exports/{session_id}/    → generated PDFs
```

---

## React Components

### Layout
- `<App />` — Router, session state provider, mode controller
- `<Header />` — Logo, mode indicator, session timer
- `<Footer />` — Disclaimer, attribution

### Landing
- `<LandingPage />` — Branding, dual CTA, disclaimer
- `<VisitSetup />` — Patient context form, mic selector, start recording

### In-Room (Mode 1)
- `<InRoomLayout />` — Two-panel split
- `<TranscriptPanel />` — Scrolling live transcript
- `<TranscriptChunk />` — Single segment (speaker, text, time)
- `<RecordingControls />` — Record/pause/end, audio level, timer
- `<AgentSidebar />` — Container for all real-time outputs
- `<AlertsSection />` — Pinned alerts
- `<AlertCard />` — Single alert with priority
- `<MedicationSection />` — Running med list with interaction status
- `<MedicationCard />` — Single med with interaction badge
- `<DifferentialSection />` — Ranked differential, live-updating
- `<SOAPDraftSection />` — Collapsible live SOAP preview
- `<PendingOrdersSection />` — Pre-filled orders with CPT
- `<ImageUploadInline />` — Upload without interrupting recording

### Post-Visit (Mode 2)
- `<PostVisitLayout />` — Two-panel: editor + tools
- `<SOAPEditor />` — Editable SOAP with section headers
- `<SOAPSection />` — Single editable section (S/O/A/P)
- `<TranscriptReference />` — Expandable/searchable full transcript
- `<CodePanel />` — ICD-10 + CPT suggestions
- `<CodeCard />` — Single code with confirm/remove
- `<MedicationSummary />` — Full med list with interactions
- `<FollowUpPanel />` — Follow-up checklist
- `<FollowUpCard />` — Single follow-up item
- `<ImageAnalysisPanel />` — Image results + similar cases
- `<ImageMatchCard />` — Reference image + condition + score
- `<PatientSummaryPanel />` — Generated summary, editable
- `<ExportBar />` — PDF download, clipboard, QR
- `<ApproveButton />` — Locks note, enables export

### Shared
- `<LoadingSpinner />` — During inference
- `<ErrorBoundary />` — Error handling
- `<FeedbackPrompt />` — Judge feedback widget

---

## Security & Deployment

### Competition Demo
All models on GPU cloud instance. Frontend on Vercel. No real patient data.

### Production Model
```
Clinic device (tablet/laptop)
    │ HTTPS (TLS 1.3)
    ▼
Hospital VPC / On-Prem Server
    ├── FastAPI orchestrator
    ├── MedASR (105M, CPU)
    ├── MedGemma-27b-text-it (GPU)
    ├── MedGemma-4b-it (GPU)
    ├── MedSigLIP + FAISS (CPU)
    └── Session store (RAM only)
```

### Privacy Guarantees
- Audio never leaves the network — MedASR runs locally
- No transcripts persisted — session-only, RAM, TTL expiry
- No PHI stored — stateless by design
- No model telemetry — open-weight models do not phone home
- All four models are open-weight — zero external API dependencies

---

## Tickets

### T-001: Project Scaffolding ✅
**Description:** Initialize React frontend and FastAPI backend with project structure.
**AC:**
- React app runs locally with hot reload
- FastAPI server runs locally, returns 200 on `/health`
- WebSocket support configured for streaming transcript
- CORS configured
- Single README with setup instructions

### T-002: Session Management ✅
**Description:** Create in-memory session store for visit state.
**AC:**
- `POST /session` creates session, returns ID
- `GET /session/{id}` returns full state
- Session expires after 2 hours
- Tracks current mode (in_room / post_visit)

### T-003: Landing Page + Visit Setup ✅
**Description:** Build entry point and visit configuration screen.
**AC:**
- Dual CTA: "Start Visit" / "Resume Post-Visit Review"
- Visit setup form: patient name, visit type, chief complaint
- Microphone permission request
- Disclaimer acknowledgment required
- Session created on "Start Recording"

### T-004: Audio Capture ✅
**Description:** Capture audio from browser mic and stream chunks to backend.
**AC:**
- MediaRecorder API captures from selected input
- Chunked at 5-second intervals
- Sent via WebSocket or HTTP POST
- Pause/resume functionality
- Visual: recording indicator, audio level, elapsed time

### T-005: Tool — transcribe ✅
**Description:** Process audio chunks through MedASR.
**AC:**
- Accepts raw audio bytes
- MedASR returns text + timestamps
- Speaker diarization best-effort
- Returns TranscriptChunk object
- Latency under 2 seconds per chunk

### T-006: Live Transcript Display ✅
**Description:** Display streaming transcript in left panel.
**AC:**
- Renders chunks as they arrive
- Speaker labels (DR: / PT:) when available
- Timestamps per chunk
- Auto-scrolls, manually scrollable

### T-007: Orchestrator — Real-Time Chunk Processing ✅
**Description:** Central orchestrator that processes chunks and decides tool calls.
**AC:**
- Receives each TranscriptChunk
- Calls `process_chunk` → MedGemma-27b-text-it
- Implements decision points D1–D9
- Routes outputs to sidebar sections
- Maintains running clinical context (structured, not full transcript)
- Updates SOAP draft as data arrives

### T-008: Tool — extract_medications ✅
**Description:** Extract structured medication data from chunks.
**AC:**
- Accepts chunk text only
- Returns Medication objects
- Handles patient-reported and doctor-prescribed
- Accumulated in session

### T-009: Tool — check_interactions ✅
**Description:** Check medication list for interactions.
**AC:**
- Accepts medication list only
- Returns InteractionFlag objects
- Triggers on medication list change
- Green confirmation when clean

### T-010: Tool — build_differential ✅
**Description:** Build running differential from accumulated symptoms.
**AC:**
- Accepts structured symptom + history data
- Returns ranked differential
- Updates as new data arrives

### T-011: Agent Sidebar ✅
**Description:** Right panel displaying all real-time agent outputs.
**AC:**
- Sections: Alerts, Medications, Differential, Draft SOAP, Pending Orders, Upload Image
- Each section updates independently
- Alerts pinned to top
- Collapsible sections

### T-012: Live SOAP Draft ✅
**Description:** Continuously build SOAP sections from transcript data.
**AC:**
- `draft_soap_section` callable per section
- S/O/A/P update as data accumulates
- Read-only in Mode 1, editable in Mode 2
- Persists through mode transition

### T-013: Tool — analyze_image + search_similar ✅
**Description:** Analyze uploaded images and search similar cases.
**AC:**
- `analyze_image` → MedGemma-4b-it → clinical description
- `search_similar` → MedSigLIP + FAISS → top-3 matches
- Works in both modes
- Findings suggested for SOAP Objective

### T-014: Image Upload (Inline) ✅
**Description:** Image upload during active recording.
**AC:**
- Upload button in sidebar
- Camera capture + file upload
- Recording continues uninterrupted
- Results appear in sidebar after processing

### T-015: End Visit + Mode Transition ✅
**Description:** Handle visit ending and Mode 1 → Mode 2 transition.
**AC:**
- "End Visit" stops recording
- Final chunk processed
- Agent runs final SOAP assembly
- Session mode updated
- UI transitions to Post-Visit layout

### T-016: SOAP Editor (Post-Visit) ✅
**Description:** Editable SOAP note for doctor review.
**AC:**
- Four sections pre-populated from live draft
- Each section editable
- Edit triggers agent re-evaluation suggestion
- Full transcript available as reference
- Track changes view

### T-017: Tool — extract_icd10_codes + extract_cpt_codes ✅
**Description:** Extract billing codes from SOAP.
**AC:**
- ICD-10 from assessment, CPT from plan
- Codes with descriptions + confidence
- Selectable list: doctor confirms/removes
- Linked to source sections

### T-018: Tool — generate_patient_summary ✅
**Description:** Generate plain-language visit summary.
**AC:**
- Accepts structured data only
- 6th-grade reading level
- Includes: summary, new meds, follow-ups, when to seek care
- Editable before export

### T-019: Follow-Up Panel ✅
**Description:** Extract and display follow-up plan.
**AC:**
- Returns FollowUpItem objects
- Checklist: action, type, timeframe
- Doctor confirms/modifies

### T-020: Export & PDF Generation ✅
**Description:** Generate exportable documents.
**AC:**
- "Approve" locks SOAP
- SOAP PDF, patient summary PDF
- Copy to clipboard for EHR
- QR code on PDF (time-limited link)

### T-021: FAISS Index Build Script ✅
**Description:** Preprocess atlas and build FAISS index.
**AC:**
- Loads atlas images
- Embeds via MedSigLIP-448
- Saves faiss_index.bin + metadata JSON
- Reproducible and documented

### T-022: Prompt Engineering ✅
**Description:** Author all system prompts for each tool.
**AC:**
- Prompts for: chunk processing, med extraction, interactions, differential, SOAP drafting, codes, patient summary
- Schema-conforming output
- Version-controlled config
- Edge cases tested

### T-023: Error Handling & Loading States ✅
**Description:** Graceful errors and loading indicators.
**AC:**
- Error handling on all API calls
- ErrorBoundary for rendering
- Non-blocking loading in Mode 1
- Audio failure handling (mic disconnect, permission revoked)

### T-024: Red Flag Alerts ✅
**Description:** Detect and surface urgent findings in real-time.
**AC:**
- Detects red flag combinations from transcript
- Prominent sidebar alert with recommendation
- Non-intrusive — informational only

### T-025: Mental Health Detection ✅
**Description:** Detect mental health signals and suggest screening.
**AC:**
- Detects mood/sleep/appetite/hopelessness mentions
- Sidebar: "Consider PHQ-2/GAD-2"
- Verbal screening scored from transcript
- Results in SOAP and follow-up

### T-026: Deployment ✅
**Description:** Deploy with stable public URLs.
**AC:**
- Frontend on Vercel
- Backend on GPU cloud (HTTPS)
- All four models loaded
- WebSocket connections stable
- End-to-end flow works

### T-032: Pyannote Integration ✅
**Description:** Install pyannote.audio, load speaker-diarization-3.1 pipeline.
**AC:** Loads model, outputs RTTM segments, supports min/max speakers, runs on CPU.

### T-033: Audio Chunk Diarization Pipeline ✅
**Description:** Run pyannote + MedASR in parallel, align by temporal overlap.
**AC:** Both models receive same chunk, alignment by max overlap, edge cases handled.

### T-034: Speaker Label Accumulation ✅
**Description:** Session-level speaker registry with embedding-based consistency.
**AC:** Cosine similarity matching, consistent IDs across chunks, 2-8 speakers.

### T-035: Speaker Role Assignment ✅
**Description:** MedGemma infers roles (doctor, patient, etc.) from labeled exchanges.
**AC:** After ~5 exchanges, assigns roles, doctor can correct, re-evaluates on new speaker.

### T-036: Transcript Display with Speaker Labels ✅
**Description:** Color-coded speaker-attributed transcript with role reassignment.
**AC:** Color-coded by speaker/role, clickable labels for manual reassignment, legend bar.

### T-037: Update Orchestrator for Speaker-Aware Routing ✅
**Description:** Speaker identity drives SOAP routing and medication source tagging.
**AC:** Patient→Subjective, Doctor→Objective/Plan, source tagging, D1-D9 updated.

### T-038: Swap MedGemma-4b-it → MedGemma-1.5-4b-it ✅
**Description:** Drop-in replacement of all `google/medgemma-4b-it` refs with `google/medgemma-1.5-4b-it`.
**AC:** Model loads from 1.5 variant, analyze_image works, docs updated.

### T-039: Tool — extract_lab_values ✅
**Description:** Vision tool extracts structured lab data from report images using MedGemma-1.5-4b-it.
**AC:** Structured JSON output (test, value, unit, reference_range, flag), handles common panels, graceful failure.

### T-040: Lab Report Upload UI (In-Room) ✅
**Description:** Lab report upload in Mode 1 sidebar, separate from image upload.
**AC:** Upload button, camera capture, preview, structured results in sidebar, recording uninterrupted.

### T-041: Lab Results Sidebar Section ✅
**Description:** Collapsible LabResultsSection displaying extracted lab values in table format.
**AC:** Table with flag styling (normal=green, high=red, low=amber, critical=bold red), multiple reports accumulate.

### T-042: Lab Results → SOAP Objective Integration ✅
**Description:** Auto-insert lab values into SOAP Objective as clinical shorthand.
**AC:** Formatted as "Labs (CBC): WBC 11.2 (H), Hgb 13.8, Plt 245", abnormal flagged.

### T-043: Lab-Aware Orchestrator Alerts ✅
**Description:** Cross-reference abnormal labs with meds/symptoms to generate clinical alerts.
**AC:** Meaningful correlations only (e.g., elevated creatinine + NSAID → caution alert).

### T-044: Lab Report Upload UI (Post-Visit) ✅
**Description:** Same upload capability in Mode 2 Tools & Outputs panel.
**AC:** Upload button, same pipeline as T-039, results in dedicated panel.

### T-045: Lab Data Models ✅
**Description:** LabReport, LabResult, LabFlag models added to session state.
**AC:** Pydantic + TypeScript models, Session.lab_reports field, persists through mode transition.

### T-027: Demo Video
**Description:** 3-minute video of full workflow.
**AC:**
- Shows: setup → transcription → real-time alerts → SOAP → review → export
- Medication interaction detection shown
- Image upload shown
- Code extraction and patient summary shown
- Under 3 minutes, clear narration

### T-028: Competition Writeup ✅
**Description:** 3-page writeup per competition template.
**AC:**
- Template: Project name, Team, Problem statement, Solution, Technical details
- All four HAI-DEF models covered
- Agentic workflow design explained
- Links to code, demo, video
- Under 3 pages

### T-029: Impact Research ✅
**Description:** Concrete impact numbers for writeup/video.
**AC:**
- Cited: 2 hours documentation per 1 hour patient care
- Cited: documentation as #1 physician burnout cause
- Cited: medical scribes cost $36-50k/year
- Projected savings with methodology

### T-030: Performance Benchmarks ✅
**Description:** Latency and quality metrics.
**AC:**
- MedASR latency per chunk (p50, p95)
- Tool call latency per tool
- End-to-end: audio → sidebar update
- SOAP quality evaluation

### T-031: Feedback Prompt ✅
**Description:** Judge feedback widget.
**AC:**
- 1-5 stars + optional comment
- On export screen
- Logs to simple store

---

## Intentional Cuts
- No model fine-tuning (models as-is; time invested in real-time UX)
- No user authentication
- No EHR integration (copy-to-clipboard as bridge)
- No persistent storage (RAM-only, TTL expiry)
- No multi-language (future work)
- No native app (web, optimized for tablet)
- No speaker diarization guarantee (best-effort)
- No real billing system (codes are suggestions only)
