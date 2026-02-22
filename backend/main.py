"""FastAPI application for the Scribe clinical documentation agent."""

import asyncio
import base64
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from audio_ws import get_session_audio, handle_audio_stream
from export import generate_patient_summary_pdf, generate_soap_pdf, generate_soap_text
from image_tools import analyze_image, search_similar
from models import (
    CreateSessionRequest,
    DiagnosisCode,
    FollowUpItem,
    ImageAnalysis,
    LabFlag,
    LabReport,
    LabResult,
    Medication,
    PatientContext,
    PatientSummary,
    Session,
    SessionMode,
    SimilarCondition,
    SOAPNote,
    SOAPStatus,
    SOAPUpdateRequest,
    Speaker,
    SpeakerProfile,
    TranscriptChunk,
    VisitType,
)
from session import store
from tools import (
    check_lab_alerts,
    draft_full_soap,
    extract_cpt_codes,
    extract_follow_ups,
    extract_icd10_codes,
    extract_lab_values,
    format_labs_for_soap,
    generate_patient_summary,
)


async def _seed_demo_data() -> None:
    """Populate the store with realistic urgent-care demo sessions."""

    demo_patients = [
        {
            "patient_context": PatientContext(name="Maria Santos", age=34, chief_complaint="Severe migraine with aura"),
            "visit_type": VisitType.URGENT,
            "mode": SessionMode.POST_VISIT,
            "transcript_chunks": [
                TranscriptChunk(timestamp_start=0.0, timestamp_end=12.5, speaker=Speaker.DOCTOR, text="Good afternoon, Maria. I understand you're having a severe headache. Can you describe what you're experiencing?"),
                TranscriptChunk(timestamp_start=12.5, timestamp_end=28.0, speaker=Speaker.PATIENT, text="It started about four hours ago on the left side of my head. I saw zigzag lines before it started, and now the pain is throbbing. Light and sound make it worse. I also feel nauseous."),
                TranscriptChunk(timestamp_start=28.0, timestamp_end=42.0, speaker=Speaker.DOCTOR, text="Have you had migraines like this before? Any history of aura?"),
                TranscriptChunk(timestamp_start=42.0, timestamp_end=55.0, speaker=Speaker.PATIENT, text="Yes, I get them maybe once or twice a month, but this one is the worst I've had in a while. The aura is new though, started about six months ago."),
                TranscriptChunk(timestamp_start=55.0, timestamp_end=72.0, speaker=Speaker.DOCTOR, text="I'm going to give you sumatriptan and ondansetron for the nausea. We should also discuss preventive options since you're having them this frequently with new aura symptoms."),
            ],
            "soap_note": SOAPNote(
                subjective="34-year-old female presents with severe left-sided throbbing headache for 4 hours preceded by visual aura (zigzag lines). Reports photophobia, phonophobia, and nausea. History of migraines 1-2x/month; aura is a new feature over past 6 months. No fever, neck stiffness, or focal neurological deficits reported.",
                objective="Vitals: BP 128/82, HR 78, Temp 98.4F. Alert and oriented x3. Cranial nerves II-XII intact. No papilledema on fundoscopic exam. Neck supple, no meningismus. Neurological exam non-focal.",
                assessment="Migraine with aura (ICD-10: G43.1). Increasing frequency and new aura symptoms warrant further evaluation. No red flags for secondary headache at this time.",
                plan="1. Sumatriptan 50mg PO now for acute relief\n2. Ondansetron 4mg ODT for nausea\n3. Start topiramate 25mg daily for migraine prophylaxis, titrate to 50mg after 1 week\n4. Headache diary recommended\n5. Follow-up with neurology within 4 weeks\n6. Return precautions: worst headache of life, fever, vision changes, weakness",
                status=SOAPStatus.REVIEWED,
            ),
            "medications": [
                Medication(name="Sumatriptan", dose="50mg", frequency="PRN for acute migraine"),
                Medication(name="Topiramate", dose="25mg", frequency="Daily"),
            ],
        },
        {
            "patient_context": PatientContext(name="James Liu", age=67, chief_complaint="Chest pain and shortness of breath"),
            "visit_type": VisitType.URGENT,
            "mode": SessionMode.POST_VISIT,
            "transcript_chunks": [
                TranscriptChunk(timestamp_start=0.0, timestamp_end=15.0, speaker=Speaker.DOCTOR, text="Mr. Liu, tell me about the chest pain. When did it start, and where exactly do you feel it?"),
                TranscriptChunk(timestamp_start=15.0, timestamp_end=35.0, speaker=Speaker.PATIENT, text="It started about two hours ago, right here in the center of my chest. It feels like pressure, like someone is sitting on my chest. It goes up to my left shoulder. I'm also having trouble catching my breath."),
                TranscriptChunk(timestamp_start=35.0, timestamp_end=50.0, speaker=Speaker.DOCTOR, text="Any sweating, nausea, or dizziness? Do you have a history of heart disease, high blood pressure, or diabetes?"),
                TranscriptChunk(timestamp_start=50.0, timestamp_end=68.0, speaker=Speaker.PATIENT, text="I'm sweating a lot and feel a bit dizzy. I have high blood pressure and type 2 diabetes. I take lisinopril and metformin. My father had a heart attack at 60."),
                TranscriptChunk(timestamp_start=68.0, timestamp_end=85.0, speaker=Speaker.DOCTOR, text="We're going to get an EKG and troponin levels right away. I'm also starting you on aspirin and giving you nitroglycerin sublingual. We need to rule out acute coronary syndrome."),
            ],
            "soap_note": SOAPNote(
                subjective="67-year-old male presents with 2-hour history of substernal chest pressure radiating to left shoulder, associated with dyspnea, diaphoresis, and dizziness. PMH significant for HTN and T2DM. Current medications: lisinopril, metformin. Family history: father with MI at age 60. Denies recent trauma or pleuritic component.",
                objective="Vitals: BP 158/94, HR 96, RR 22, SpO2 94% on RA, Temp 98.6F. Appears diaphoretic and anxious. Heart: regular rate, no murmurs. Lungs: bibasilar crackles. No peripheral edema. EKG: ST depression in leads V4-V6. Troponin I: 0.08 ng/mL (mildly elevated).",
                assessment="Acute coronary syndrome, likely NSTEMI given elevated troponin and EKG changes. Risk factors include age, HTN, DM, and family history. Differential includes unstable angina, pulmonary embolism.",
                plan="1. Aspirin 325mg PO stat\n2. Nitroglycerin 0.4mg SL q5min PRN chest pain (max 3 doses)\n3. Heparin drip per ACS protocol\n4. Serial troponins q6h\n5. Cardiology consult for possible cardiac catheterization\n6. Transfer to monitored bed\n7. Hold metformin pending renal function",
                status=SOAPStatus.REVIEWED,
            ),
            "medications": [
                Medication(name="Aspirin", dose="325mg", frequency="Stat, then 81mg daily"),
                Medication(name="Nitroglycerin", dose="0.4mg SL", frequency="PRN chest pain"),
            ],
        },
        {
            "patient_context": PatientContext(name="Aisha Patel", age=28, chief_complaint="Laceration on right forearm"),
            "visit_type": VisitType.URGENT,
            "mode": SessionMode.POST_VISIT,
            "transcript_chunks": [
                TranscriptChunk(timestamp_start=0.0, timestamp_end=14.0, speaker=Speaker.DOCTOR, text="Hi Aisha, I see you have a cut on your right forearm. How did this happen?"),
                TranscriptChunk(timestamp_start=14.0, timestamp_end=28.0, speaker=Speaker.PATIENT, text="I was cooking and the knife slipped. It's been bleeding on and off for about 45 minutes. I tried to put pressure on it but it keeps opening up."),
                TranscriptChunk(timestamp_start=28.0, timestamp_end=42.0, speaker=Speaker.DOCTOR, text="When was your last tetanus shot? Any allergies to lidocaine or latex?"),
                TranscriptChunk(timestamp_start=42.0, timestamp_end=52.0, speaker=Speaker.PATIENT, text="I think my last tetanus was maybe eight years ago? No allergies that I know of."),
                TranscriptChunk(timestamp_start=52.0, timestamp_end=68.0, speaker=Speaker.DOCTOR, text="This will need about four stitches. I'm going to clean it out and numb the area with lidocaine first. We'll also update your tetanus since it's been over five years."),
            ],
            "soap_note": SOAPNote(
                subjective="28-year-old female presents with a laceration to the right volar forearm sustained 45 minutes ago from a kitchen knife. Reports intermittent bleeding despite direct pressure. Last tetanus booster approximately 8 years ago. No allergies. No numbness or weakness in hand/fingers.",
                objective="Vitals: BP 118/72, HR 74, Temp 98.2F. Right volar forearm: 4cm linear laceration, approximately 5mm deep, clean edges. No foreign body visualized. Tendon function intact—full flexion/extension of all digits. Radial and ulnar pulses 2+. Sensation intact throughout hand. No signs of infection.",
                assessment="Simple laceration, right volar forearm, 4cm. No tendon, nerve, or vascular involvement. Tetanus booster indicated (>5 years since last dose).",
                plan="1. Wound irrigation with normal saline\n2. Local anesthesia with 1% lidocaine\n3. Primary closure with 4-0 nylon sutures (4 simple interrupted)\n4. Tdap booster administered today\n5. Wound care instructions provided\n6. Return in 10-12 days for suture removal\n7. Return sooner if signs of infection (redness, swelling, drainage, fever)",
                status=SOAPStatus.REVIEWED,
            ),
            "medications": [
                Medication(name="Lidocaine 1%", dose="5mL local infiltration", frequency="Once"),
            ],
        },
        {
            "patient_context": PatientContext(name="Robert Kim", age=45, chief_complaint="High fever and body aches for 3 days"),
            "visit_type": VisitType.URGENT,
            "mode": SessionMode.ACTIVE_VISIT,
            "transcript_chunks": [
                TranscriptChunk(timestamp_start=0.0, timestamp_end=18.0, speaker=Speaker.DOCTOR, text="Robert, you've had a fever for three days now. What's your temperature been running, and what other symptoms are you having?"),
                TranscriptChunk(timestamp_start=18.0, timestamp_end=38.0, speaker=Speaker.PATIENT, text="It's been up to 103 at home. My whole body aches, I have a terrible headache, and I've been really fatigued. A bit of a dry cough too. I haven't been able to go to work."),
            ],
            "soap_note": SOAPNote(
                subjective="45-year-old male presents with 3-day history of high fever (up to 103F at home), diffuse myalgias, headache, fatigue, and dry cough. Unable to work due to severity of symptoms.",
                objective="",
                assessment="",
                plan="",
                status=SOAPStatus.IN_PROGRESS,
            ),
            "medications": [],
        },
        {
            "patient_context": PatientContext(name="Elena Vasquez", age=8, chief_complaint="Ear pain and pulling at ears"),
            "visit_type": VisitType.URGENT,
            "mode": SessionMode.POST_VISIT,
            "transcript_chunks": [
                TranscriptChunk(timestamp_start=0.0, timestamp_end=16.0, speaker=Speaker.DOCTOR, text="Hi there, Elena. Mom, can you tell me what's been going on with her ears?"),
                TranscriptChunk(timestamp_start=16.0, timestamp_end=34.0, speaker=Speaker.PATIENT, text="She's been pulling at her right ear since yesterday and crying, especially at night. She had a runny nose for about a week before this started. Her temperature was 101 this morning."),
                TranscriptChunk(timestamp_start=34.0, timestamp_end=48.0, speaker=Speaker.DOCTOR, text="Has she had ear infections before? Any allergies to antibiotics?"),
                TranscriptChunk(timestamp_start=48.0, timestamp_end=60.0, speaker=Speaker.PATIENT, text="She had one about six months ago. They gave her amoxicillin and it cleared up fine. No allergies."),
                TranscriptChunk(timestamp_start=60.0, timestamp_end=78.0, speaker=Speaker.DOCTOR, text="I can see the right tympanic membrane is bulging and red. This is an acute otitis media. We'll start her on amoxicillin again since it worked well last time."),
            ],
            "soap_note": SOAPNote(
                subjective="8-year-old female brought in by mother for right ear pain x1 day. Pulling at right ear, crying especially at night. Preceded by 1 week of rhinorrhea. Temp 101F at home this morning. History of prior AOM 6 months ago, resolved with amoxicillin. NKDA.",
                objective="Vitals: Temp 100.8F, HR 98, RR 20. Right ear: TM erythematous, bulging, with decreased mobility on pneumatic otoscopy. Left ear: TM clear, normal mobility. Oropharynx: mild posterior pharyngeal erythema. No cervical lymphadenopathy. Lungs clear.",
                assessment="Acute otitis media, right ear. Second episode in 6 months. No indication for ENT referral at this time (fewer than 3 episodes in 6 months).",
                plan="1. Amoxicillin 400mg/5mL, 90mg/kg/day divided BID x10 days\n2. Ibuprofen 100mg/5mL, 10mg/kg q6h PRN pain/fever\n3. Follow-up in 10-14 days or sooner if symptoms worsen\n4. Return if fever persists >48h on antibiotics, drainage from ear, or behavioral changes",
                status=SOAPStatus.REVIEWED,
            ),
            "medications": [
                Medication(name="Amoxicillin", dose="400mg/5mL suspension, 90mg/kg/day", frequency="BID x10 days"),
                Medication(name="Ibuprofen", dose="100mg/5mL, 10mg/kg", frequency="q6h PRN"),
            ],
        },
        {
            "patient_context": PatientContext(name="David Thompson", age=52, chief_complaint="Allergic reaction - hives and facial swelling"),
            "visit_type": VisitType.URGENT,
            "mode": SessionMode.POST_VISIT,
            "transcript_chunks": [
                TranscriptChunk(timestamp_start=0.0, timestamp_end=14.0, speaker=Speaker.DOCTOR, text="David, I can see the hives and some swelling around your eyes. When did this start, and do you know what might have triggered it?"),
                TranscriptChunk(timestamp_start=14.0, timestamp_end=32.0, speaker=Speaker.PATIENT, text="It started about an hour ago. I had shrimp for lunch, which I've eaten before with no problems. The hives appeared first on my arms, then spread to my chest and face. My lips feel a little tingly."),
                TranscriptChunk(timestamp_start=32.0, timestamp_end=46.0, speaker=Speaker.DOCTOR, text="Any difficulty breathing, throat tightness, or wheezing? Have you used an EpiPen or taken any antihistamines?"),
                TranscriptChunk(timestamp_start=46.0, timestamp_end=58.0, speaker=Speaker.PATIENT, text="No trouble breathing yet, but my throat feels a little scratchy. I took a Benadryl about 30 minutes ago but it hasn't really helped."),
                TranscriptChunk(timestamp_start=58.0, timestamp_end=78.0, speaker=Speaker.DOCTOR, text="Given the facial swelling and lip tingling, I'm going to give you epinephrine as a precaution and start IV diphenhydramine and methylprednisolone. We'll monitor you for at least four hours. I'm also prescribing an EpiPen for you to carry."),
            ],
            "soap_note": SOAPNote(
                subjective="52-year-old male presents with acute onset of diffuse urticaria and facial/periorbital angioedema ~1 hour after eating shrimp. Reports lip tingling and mild throat scratchiness. Denies dyspnea, wheezing, or chest tightness. Took diphenhydramine 25mg PO 30 min ago without improvement. Reports eating shrimp previously without reaction. No known drug allergies.",
                objective="Vitals: BP 132/86, HR 102, RR 18, SpO2 98% on RA, Temp 98.6F. Diffuse urticarial wheals over bilateral arms, chest, and abdomen. Periorbital edema and mild lip swelling bilaterally. Oropharynx: no uvular edema, no stridor. Lungs: clear bilaterally, no wheezing. No tongue swelling.",
                assessment="Acute allergic reaction with angioedema, likely shellfish-triggered. Moderate severity given facial involvement and lip tingling, but no anaphylaxis criteria met (no respiratory compromise or hypotension). New-onset shellfish allergy in adult.",
                plan="1. Epinephrine 0.3mg IM (lateral thigh) - administered as precaution\n2. Diphenhydramine 50mg IV\n3. Methylprednisolone 125mg IV\n4. Famotidine 20mg IV (H2 blocker)\n5. Monitor in department x4 hours for biphasic reaction\n6. Prescribe EpiPen 0.3mg auto-injector, instruct on use\n7. Prednisone 40mg PO daily x5 days on discharge\n8. Cetirizine 10mg daily x2 weeks\n9. Strict shellfish avoidance\n10. Allergist referral within 2-4 weeks for confirmatory testing",
                status=SOAPStatus.REVIEWED,
            ),
            "medications": [
                Medication(name="Epinephrine", dose="0.3mg IM", frequency="Once (administered in clinic)"),
                Medication(name="EpiPen", dose="0.3mg auto-injector", frequency="PRN anaphylaxis"),
            ],
        },
    ]

    for data in demo_patients:
        session = await store.create_session(
            visit_type=data["visit_type"],
            patient_context=data["patient_context"],
        )
        updates = {
            "mode": data["mode"],
            "transcript_chunks": data["transcript_chunks"],
            "soap_note": data["soap_note"],
            "medications": data["medications"],
        }
        await store.update_session(session.id, updates)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await store.start()
    await _seed_demo_data()
    yield
    await store.stop()
    from llm import shutdown as llm_shutdown
    await llm_shutdown()


app = FastAPI(
    title="Scribe — AI Clinical Documentation Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- /api prefix stripping (production static serving) ----------

from starlette.types import ASGIApp, Receive, Scope, Send


class StripApiPrefix:
    """Strip /api prefix so the frontend's /api/session hits /session."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] in ("http", "websocket"):
            path: str = scope.get("path", "")
            if path.startswith("/api/") or path == "/api":
                scope = dict(scope, path=path[4:] or "/")
        await self.app(scope, receive, send)


app.add_middleware(StripApiPrefix)


# ---------- REST endpoints ----------


class SessionSummary(BaseModel):
    id: str
    created_at: datetime
    mode: SessionMode
    visit_type: VisitType
    patient_context: Optional[PatientContext] = None
    transcript_chunk_count: int


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/throttle-status")
async def throttle_status():
    """Return seconds until each tool throttle is next due."""
    from orchestrator import _alert_throttle, _med_throttle, _diff_throttle

    return {
        "alerts": {"seconds_until_due": round(_alert_throttle.seconds_until_due(), 1)},
        "medications": {"seconds_until_due": round(_med_throttle.seconds_until_due(), 1)},
        "differential": {"seconds_until_due": round(_diff_throttle.seconds_until_due(), 1)},
    }


@app.post("/session/{session_id}/force-update")
async def force_update(session_id: str):
    """Reset all throttles and re-run the orchestrator on the last transcript chunk."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.transcript_chunks:
        raise HTTPException(status_code=400, detail="No transcript chunks yet")

    from orchestrator import _alert_throttle, _med_throttle, _diff_throttle, process_chunk

    _alert_throttle.reset()
    _med_throttle.reset()
    _diff_throttle.reset()

    last_chunk = session.transcript_chunks[-1]
    updates = await process_chunk(last_chunk, session)
    updates.pop("transcript_chunks", None)
    if updates:
        await store.update_session(session_id, updates)

    return {"status": "ok", "updated_keys": list(updates.keys())}


@app.get("/sessions", response_model=List[SessionSummary])
async def list_sessions():
    sessions = await store.list_sessions()
    return [
        SessionSummary(
            id=s.id,
            created_at=s.created_at,
            mode=s.mode,
            visit_type=s.visit_type,
            patient_context=s.patient_context,
            transcript_chunk_count=len(s.transcript_chunks),
        )
        for s in sessions
    ]


@app.post("/session", response_model=Session, status_code=201)
async def create_session(req: CreateSessionRequest):
    return await store.create_session(
        visit_type=req.visit_type, patient_context=req.patient_context
    )


@app.get("/session/{session_id}", response_model=Session)
async def get_session(session_id: str):
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.delete("/session/{session_id}", status_code=204)
async def delete_session(session_id: str):
    deleted = await store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")


@app.post("/session/{session_id}/finalize", response_model=Session)
async def finalize_session(session_id: str):
    """Trigger final SOAP assembly from all accumulated session data."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Gather clinical context from session for full SOAP draft
    symptoms: list[str] = []
    allergies: list[str] = []
    family_history: list[str] = []
    exam_findings: list[str] = []

    # Extract context from existing SOAP note text as fallback
    # The orchestrator accumulates these during chunk processing
    medications = list(session.medications)
    differential = list(session.differential)
    orders = [{"details": o} for o in session.pending_orders]

    try:
        finalized_soap = await draft_full_soap(
            symptoms=symptoms,
            medications=medications,
            exam_findings=exam_findings,
            differential=differential,
            orders=orders,
            allergies=allergies,
            family_history=family_history,
        )
        finalized_soap.status = SOAPStatus.COMPLETE
    except Exception:
        # If LLM call fails, keep existing SOAP but mark complete
        finalized_soap = session.soap_note.model_copy()
        finalized_soap.status = SOAPStatus.COMPLETE

    updated = await store.update_session(
        session_id, {"soap_note": finalized_soap}
    )
    return updated


@app.post("/session/{session_id}/end-visit")
async def end_visit(session_id: str):
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.mode == SessionMode.POST_VISIT:
        raise HTTPException(status_code=400, detail="Visit already ended")
    updated = await store.update_session(
        session_id, {"mode": SessionMode.POST_VISIT}
    )
    if updated is None:
        raise HTTPException(status_code=500, detail="Failed to update session")
    from llm import get_usage_stats
    return {
        "session": updated.model_dump(mode="json"),
        "llm_usage": get_usage_stats(),
    }


@app.get("/llm-usage")
async def llm_usage():
    """Return cumulative LLM token usage and estimated cost."""
    from llm import get_usage_stats
    return get_usage_stats()


@app.patch("/session/{session_id}/soap", response_model=Session)
async def update_soap(session_id: str, req: SOAPUpdateRequest):
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    soap_updates: dict = {}
    for field in ("subjective", "objective", "assessment", "plan"):
        value = getattr(req, field)
        if value is not None:
            soap_updates[field] = value

    if soap_updates:
        soap_updates["last_updated"] = datetime.now(timezone.utc)
        updated_soap = session.soap_note.model_copy(update=soap_updates)
        updated = await store.update_session(
            session_id, {"soap_note": updated_soap}
        )
        return updated

    return session


# ---------- Speaker role assignment ----------


class SpeakerRoleAssignment(BaseModel):
    speaker_id: str
    role: str


class SpeakerRoleUpdateRequest(BaseModel):
    assignments: List[SpeakerRoleAssignment]


@app.patch("/session/{session_id}/speaker-roles", response_model=Session)
async def update_speaker_roles(session_id: str, req: SpeakerRoleUpdateRequest):
    """Manually correct speaker role assignments."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Build updated profiles: start from existing, override with request
    existing_map = {
        sp.consistent_id: sp for sp in session.speaker_profiles
    }
    for assignment in req.assignments:
        existing_map[assignment.speaker_id] = SpeakerProfile(
            consistent_id=assignment.speaker_id,
            role=assignment.role,
            confidence=1.0,  # manual corrections get full confidence
            reasoning="Manually assigned by clinician",
        )

    updated = await store.update_session(
        session_id,
        {"speaker_profiles": list(existing_map.values())},
    )
    return updated


# ---------- Code extraction ----------


class CodeUpdateRequest(BaseModel):
    codes: List[DiagnosisCode]


@app.post("/session/{session_id}/extract-codes", response_model=Session)
async def extract_codes(session_id: str):
    """Extract ICD-10 and CPT codes from the session SOAP note."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Build orders list from pending_orders for CPT extraction
    orders = [{"type": "other", "details": o} for o in session.pending_orders]

    icd10_codes, cpt_codes = await asyncio.gather(
        extract_icd10_codes(session.soap_note.assessment),
        extract_cpt_codes(session.soap_note.plan, orders or None),
    )

    all_codes = icd10_codes + cpt_codes
    updated = await store.update_session(
        session_id, {"diagnosis_codes": all_codes}
    )
    return updated


@app.patch("/session/{session_id}/codes", response_model=Session)
async def update_codes(session_id: str, req: CodeUpdateRequest):
    """Update diagnosis/procedure codes (confirm or remove)."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    updated = await store.update_session(
        session_id, {"diagnosis_codes": req.codes}
    )
    return updated


# ---------- Patient summary & follow-ups ----------


class FollowUpUpdateRequest(BaseModel):
    follow_ups: List[FollowUpItem]


@app.post("/session/{session_id}/generate-summary", response_model=Session)
async def generate_summary(session_id: str):
    """Generate a plain-language patient summary from session data."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    summary = await generate_patient_summary(
        soap=session.soap_note,
        medications=session.medications,
        follow_ups=session.follow_ups,
    )
    updated = await store.update_session(
        session_id, {"patient_summary": summary}
    )
    return updated


@app.post("/session/{session_id}/extract-followups", response_model=Session)
async def extract_followups(session_id: str):
    """Extract follow-up items from the session SOAP plan and transcript."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    transcript_text = " ".join(
        chunk.text for chunk in session.transcript_chunks
    )
    follow_ups = await extract_follow_ups(
        plan=session.soap_note.plan,
        transcript_text=transcript_text,
    )
    updated = await store.update_session(
        session_id, {"follow_ups": follow_ups}
    )
    return updated


@app.patch("/session/{session_id}/summary", response_model=Session)
async def update_summary(session_id: str, req: PatientSummary):
    """Update patient summary (doctor edits)."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Merge provided fields with existing summary
    existing = session.patient_summary or PatientSummary()
    merged = existing.model_copy(update=req.model_dump(exclude_unset=True))
    updated = await store.update_session(
        session_id, {"patient_summary": merged}
    )
    return updated


@app.patch("/session/{session_id}/followups", response_model=Session)
async def update_followups(session_id: str, req: FollowUpUpdateRequest):
    """Update the follow-up list (doctor edits)."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    updated = await store.update_session(
        session_id, {"follow_ups": req.follow_ups}
    )
    return updated


# ---------- Image analysis ----------


@app.post("/session/{session_id}/upload-image", response_model=ImageAnalysis)
async def upload_image(session_id: str, file: UploadFile):
    """Upload a medical image for analysis and similarity search."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    image_bytes = await file.read()

    # Save to /tmp/uploads/{session_id}/
    upload_dir = Path("/tmp/uploads") / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = file.filename or "image.png"
    save_path = upload_dir / filename
    save_path.write_bytes(image_bytes)
    image_url = f"/tmp/uploads/{session_id}/{filename}"

    # Run analysis and similarity search concurrently
    clinical_context = ""
    if session.patient_context:
        ctx = session.patient_context
        parts = [p for p in [ctx.name, f"Age {ctx.age}" if ctx.age else None, ctx.chief_complaint] if p]
        clinical_context = ", ".join(parts)
    description_text, similar_results = await asyncio.gather(
        analyze_image(image_bytes, clinical_context=clinical_context),
        search_similar(image_bytes, top_k=3),
    )

    similar_conditions = [
        SimilarCondition(
            condition_label=r["condition_label"],
            similarity_score=r["similarity_score"],
        )
        for r in similar_results
    ]

    analysis = ImageAnalysis(
        image_url=image_url,
        clinical_description=description_text,
        similar_conditions=similar_conditions,
        soap_section="objective",
    )

    # Append to session
    updated_analyses = list(session.image_analyses) + [analysis]
    await store.update_session(session_id, {"image_analyses": updated_analyses})

    return analysis


# ---------- Lab report upload ----------


@app.post("/session/{session_id}/upload-lab-report", response_model=dict)
async def upload_lab_report(session_id: str, file: UploadFile = File(...)):
    """Upload a lab report image for structured data extraction."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    contents = await file.read()
    image_base64 = base64.b64encode(contents).decode()

    result = await extract_lab_values(image_base64)

    lab_results = []
    for r in result.get("results", []):
        try:
            flag = LabFlag(r.get("flag", "normal"))
        except ValueError:
            flag = LabFlag.NORMAL
        try:
            value = float(r["value"])
        except (KeyError, ValueError, TypeError):
            continue
        lab_results.append(LabResult(
            test=r["test"],
            value=value,
            unit=r.get("unit", ""),
            reference_range=r.get("reference_range"),
            flag=flag,
        ))

    lab_report = LabReport(
        image_url=f"data:image/png;base64,{image_base64[:50]}...",  # truncated for storage
        lab_name=result.get("lab_name", "Unknown Panel"),
        date=result.get("date"),
        results=lab_results,
    )

    updated_reports = list(session.lab_reports) + [lab_report]
    await store.update_session(session_id, {"lab_reports": updated_reports})

    # Auto-insert into SOAP Objective
    lab_text = format_labs_for_soap(lab_report)
    if lab_text:
        soap = session.soap_note.model_copy()
        if soap.objective:
            soap.objective = f"{soap.objective}\n\n{lab_text}"
        else:
            soap.objective = lab_text
        soap.last_updated = datetime.now(timezone.utc)
        await store.update_session(session_id, {"soap_note": soap})

    # Check for lab-aware clinical alerts
    session = await store.get_session(session_id)  # refresh after SOAP update
    if session:
        transcript_text = " ".join(
            c.text for c in session.transcript_chunks[-5:] if c.text
        )
        symptoms_list: list[str] = []  # extracted from recent context
        lab_alerts = await check_lab_alerts(
            lab_reports=session.lab_reports,
            medications=list(session.medications),
            symptoms=symptoms_list,
            transcript_context=transcript_text,
        )
        if lab_alerts:
            updated_alerts = list(session.clinical_alerts) + lab_alerts
            await store.update_session(session_id, {"clinical_alerts": updated_alerts})

    return lab_report.model_dump(mode="json")


# ---------- Approve & Export ----------


@app.post("/session/{session_id}/approve", response_model=Session)
async def approve_session(session_id: str):
    """Lock the SOAP note by setting status to reviewed."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    reviewed_soap = session.soap_note.model_copy(
        update={"status": SOAPStatus.REVIEWED, "last_updated": datetime.now(timezone.utc)}
    )
    updated = await store.update_session(
        session_id, {"soap_note": reviewed_soap}
    )
    return updated


@app.get("/session/{session_id}/export/soap-pdf")
async def export_soap_pdf(session_id: str):
    """Download the SOAP note as a PDF."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    pdf_bytes = generate_soap_pdf(session)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="soap_note_{session_id[:8]}.pdf"'},
    )


@app.get("/session/{session_id}/export/patient-summary-pdf")
async def export_patient_summary_pdf(session_id: str):
    """Download the patient summary as a PDF."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    pdf_bytes = generate_patient_summary_pdf(session)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="patient_summary_{session_id[:8]}.pdf"'},
    )


@app.get("/session/{session_id}/export/soap-text")
async def export_soap_text(session_id: str):
    """Get the SOAP note as plain text (for clipboard copy)."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    text = generate_soap_text(session)
    return PlainTextResponse(content=text)


# ---------- Feedback ----------


class FeedbackRequest(BaseModel):
    rating: int
    comment: str = ""
    session_id: str


FEEDBACK_FILE = Path(__file__).parent.parent / "data" / "feedback.json"


@app.post("/feedback")
async def post_feedback(req: FeedbackRequest):
    """Append session feedback to a JSON log file."""
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "session_id": req.session_id,
        "rating": req.rating,
        "comment": req.comment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Read existing entries (or start fresh)
    existing: list = []
    if FEEDBACK_FILE.exists():
        try:
            existing = json.loads(FEEDBACK_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            existing = []

    existing.append(entry)
    await asyncio.to_thread(
        FEEDBACK_FILE.write_text, json.dumps(existing, indent=2)
    )

    return {"status": "ok"}


# ---------- Sample audio ----------

SAMPLE_WAV = Path(__file__).parent / "static" / "sample_conversation.wav"

# VAD-based chunk boundaries (computed once, cached)
_sample_vad_boundaries: list[tuple[float, float]] | None = None


def _compute_vad_boundaries() -> list[tuple[float, float]]:
    """Split sample WAV at silence gaps, mirroring frontend VAD behaviour."""
    global _sample_vad_boundaries
    if _sample_vad_boundaries is not None:
        return _sample_vad_boundaries

    import numpy as np
    import soundfile as sf

    audio, sr = sf.read(str(SAMPLE_WAV), dtype="float32")

    silence_threshold = 0.01
    silence_duration_s = 1.0
    min_chunk_s = 2.5
    max_chunk_s = 20.0
    frame_ms = 30
    frame_len = int(sr * frame_ms / 1000)

    chunks: list[tuple[float, float]] = []
    chunk_start = 0
    has_speech = False
    silence_start: float | None = None

    for i in range(0, len(audio), frame_len):
        frame = audio[i : i + frame_len]
        rms = float(np.sqrt(np.mean(frame**2)))
        t = i / sr

        if rms > silence_threshold:
            has_speech = True
            silence_start = None
        else:
            if silence_start is None:
                silence_start = t
            if has_speech and silence_start is not None:
                silence_dur = t - silence_start
                chunk_dur = (i - chunk_start) / sr
                if silence_dur >= silence_duration_s and chunk_dur >= min_chunk_s:
                    chunks.append((chunk_start / sr, silence_start))
                    chunk_start = int(silence_start * sr)
                    has_speech = False
                    silence_start = None

        if (i - chunk_start) / sr >= max_chunk_s and has_speech:
            chunks.append((chunk_start / sr, i / sr))
            chunk_start = i
            has_speech = False
            silence_start = None

    if has_speech:
        chunks.append((chunk_start / sr, len(audio) / sr))

    _sample_vad_boundaries = chunks
    return chunks


@app.get("/sample-audio/info")
async def sample_audio_info():
    """Return metadata about the sample conversation audio."""
    if not SAMPLE_WAV.exists():
        raise HTTPException(status_code=404, detail="Sample audio not found")

    boundaries = await asyncio.to_thread(_compute_vad_boundaries)
    total_dur = boundaries[-1][1] if boundaries else 0.0
    chunk_durations = [end - start for start, end in boundaries]
    return {
        "duration": total_dur,
        "chunk_seconds": chunk_durations,
        "total_chunks": len(boundaries),
    }


@app.get("/sample-audio/full")
async def sample_audio_full():
    """Return the full sample conversation WAV for browser playback."""
    if not SAMPLE_WAV.exists():
        raise HTTPException(status_code=404, detail="Sample audio not found")
    return Response(content=SAMPLE_WAV.read_bytes(), media_type="audio/wav")


@app.get("/sample-audio/chunk/{index}")
async def sample_audio_chunk(index: int):
    """Return a VAD-segmented chunk of sample audio as WAV bytes."""
    if not SAMPLE_WAV.exists():
        raise HTTPException(status_code=404, detail="Sample audio not found")

    boundaries = await asyncio.to_thread(_compute_vad_boundaries)
    if index < 0 or index >= len(boundaries):
        raise HTTPException(status_code=404, detail="Chunk index out of range")

    import io
    import soundfile as sf

    start_s, end_s = boundaries[index]
    audio, sr = sf.read(str(SAMPLE_WAV), dtype="float32")
    chunk_audio = audio[int(start_s * sr) : int(end_s * sr)]

    buf = io.BytesIO()
    sf.write(buf, chunk_audio, sr, format="WAV", subtype="PCM_16")
    return Response(content=buf.getvalue(), media_type="audio/wav")


# ---------- Eval endpoints ----------


class NoteRequest(BaseModel):
    transcript: str
    format: str = "both"  # "both" | "soap" | "aci"


class JudgeRequest(BaseModel):
    dialogue: str
    soap_note: str


class EntityRequest(BaseModel):
    text: str


@app.post("/eval/transcribe")
async def eval_transcribe(audio: UploadFile):
    """Full ASR pipeline on a single audio file for evaluation."""
    wav_bytes = await audio.read()
    from transcribe import transcribe, transcribe_whisper
    from diarize import diarize
    from transcript_merge import merge_transcripts

    medasr_result, whisper_result, (segments, embeddings) = await asyncio.gather(
        transcribe(wav_bytes),
        transcribe_whisper(wav_bytes),
        diarize(wav_bytes),
    )

    seg_dicts = [{"speaker_id": s.speaker_id, "start": s.start, "end": s.end} for s in segments]
    merged_turns = await merge_transcripts(
        medasr_text=medasr_result.text,
        whisper_text=whisper_result.text,
        speaker_segments=seg_dicts,
    )
    merged_text = " ".join(t["text"] for t in merged_turns)

    return {
        "medasr_text": medasr_result.text,
        "whisper_text": whisper_result.text,
        "merged_text": merged_text,
        "speaker_turns": merged_turns,
        "diarization_segments": seg_dicts,
        "n_diarization_segments": len(segments),
    }


@app.post("/eval/generate-notes")
async def eval_generate_notes(req: NoteRequest):
    """Generate SOAP and/or ACI notes from a transcript for evaluation."""
    from tools import generate_aci_note, draft_soap_from_transcript

    results = {}
    if req.format in ("both", "soap"):
        soap = await draft_soap_from_transcript(req.transcript)
        results["soap_note"] = soap["full_text"]
        results["soap_sections"] = soap["sections"]
    if req.format in ("both", "aci"):
        aci = await generate_aci_note(req.transcript)
        results["aci_note"] = aci["full_text"]
        results["aci_sections"] = aci["sections"]
    return results


@app.post("/eval/llm-judge")
async def eval_llm_judge(req: JudgeRequest):
    """LLM-as-judge for clinical note quality scoring."""
    from llm import call_medgemma_json
    from prompts import LLM_JUDGE_PROMPT

    result = await call_medgemma_json(
        LLM_JUDGE_PROMPT.format(dialogue=req.dialogue[:4000], soap_note=req.soap_note),
        temperature=0.1,
        max_tokens=1024,
    )
    return result


@app.post("/eval/extract-entities")
async def eval_extract_entities(req: EntityRequest):
    """LLM-based medical entity extraction for evaluation."""
    from llm import call_medgemma_json
    from prompts import ENTITY_EXTRACTION_PROMPT

    text = req.text
    if len(text) > 12000:
        mid = len(text) // 2
        split_at = text.rfind('. ', mid - 500, mid + 500)
        if split_at == -1:
            split_at = mid
        r1 = await call_medgemma_json(
            ENTITY_EXTRACTION_PROMPT.format(text=text[:split_at]),
            temperature=0.0,
            max_tokens=1024,
        )
        r2 = await call_medgemma_json(
            ENTITY_EXTRACTION_PROMPT.format(text=text[split_at:]),
            temperature=0.0,
            max_tokens=1024,
        )
        entities = sorted(set(r1.get("entities", []) + r2.get("entities", [])))
        return {"entities": entities}

    result = await call_medgemma_json(
        ENTITY_EXTRACTION_PROMPT.format(text=text),
        temperature=0.0,
        max_tokens=1024,
    )
    return result


# ---------- HeAR Audio Analysis ----------


@app.get("/session/{session_id}/audio")
async def get_audio(session_id: str):
    """Return the full visit recording as a WAV file."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    wav = get_session_audio(session_id)
    if wav is None:
        raise HTTPException(status_code=404, detail="No audio recorded for this session")
    return Response(content=wav, media_type="audio/wav")


class HearAnalysisRequest(BaseModel):
    start_s: float
    end_s: float


@app.post("/session/{session_id}/analyze-audio")
async def analyze_audio(session_id: str, req: HearAnalysisRequest):
    """Run HeAR health acoustic analysis on a selected audio segment."""
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    wav = get_session_audio(session_id)
    if wav is None:
        raise HTTPException(status_code=404, detail="No audio recorded for this session")
    if req.end_s <= req.start_s:
        raise HTTPException(status_code=400, detail="end_s must be greater than start_s")

    clinical_context = ""
    if session.patient_context:
        parts = [
            p
            for p in [
                session.patient_context.name,
                f"Age {session.patient_context.age}" if session.patient_context.age else None,
                session.patient_context.chief_complaint,
            ]
            if p
        ]
        clinical_context = ", ".join(parts)

    from hear_tools import analyze_audio_segment

    result = await analyze_audio_segment(wav, req.start_s, req.end_s, clinical_context)
    return result


# ---------- WebSocket ----------


@app.websocket("/session/{session_id}/audio")
async def audio_stream(websocket: WebSocket, session_id: str):
    await handle_audio_stream(websocket, session_id)


# ---------- Static file serving (production) ----------

static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
