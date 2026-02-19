"""Pydantic models for the Open Attend clinical documentation agent."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class SessionMode(str, Enum):
    PRE_VISIT = "pre_visit"
    ACTIVE_VISIT = "active_visit"
    POST_VISIT = "post_visit"


class VisitType(str, Enum):
    IN_PERSON = "in_person"
    TELEHEALTH = "telehealth"
    FOLLOW_UP = "follow_up"
    NEW_PATIENT = "new_patient"
    URGENT = "urgent"


class PatientContext(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    chief_complaint: Optional[str] = None
    fhir_id: Optional[str] = None  # FHIR Patient resource ID for EHR linkage


class Speaker(str, Enum):
    PHYSICIAN = "physician"
    DOCTOR = "doctor"
    PATIENT = "patient"
    UNKNOWN = "unknown"
    OTHER = "other"


class AlertType(str, Enum):
    DRUG_INTERACTION = "drug_interaction"
    ALLERGY = "allergy"
    CONTRAINDICATION = "contraindication"
    CRITICAL_VALUE = "critical_value"
    GUIDELINE = "guideline"


class AlertPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Severity(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class SOAPStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    REVIEWED = "reviewed"


class FollowUpType(str, Enum):
    LAB = "lab"
    IMAGING = "imaging"
    REFERRAL = "referral"
    MEDICATION = "medication"
    APPOINTMENT = "appointment"
    OTHER = "other"


class ReadingLevel(str, Enum):
    ELEMENTARY = "elementary"
    MIDDLE_SCHOOL = "middle_school"
    HIGH_SCHOOL = "high_school"
    COLLEGE = "college"


# --- Core domain models ---


class TranscriptChunk(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    timestamp_start: float
    timestamp_end: float
    speaker: Speaker
    speaker_id: Optional[str] = None  # raw pyannote ID (e.g. "SPEAKER_00")
    text: str
    processed: bool = False


class Medication(BaseModel):
    name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    source: Optional[str] = None
    chunk_id: Optional[str] = None


class InteractionFlag(BaseModel):
    drug_a: str
    drug_b: str
    severity: Severity
    mechanism: Optional[str] = None
    recommendation: Optional[str] = None


class ClinicalAlert(BaseModel):
    type: AlertType
    message: str
    source_chunk_id: Optional[str] = None
    priority: AlertPriority = AlertPriority.MEDIUM
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SOAPNote(BaseModel):
    subjective: str = ""
    objective: str = ""
    assessment: str = ""
    plan: str = ""
    status: SOAPStatus = SOAPStatus.DRAFT
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DiagnosisCode(BaseModel):
    code: str
    description: str
    confidence: float = 0.0
    source_section: Optional[str] = None
    confirmed: bool = False


class SpeakerProfile(BaseModel):
    consistent_id: str  # e.g. "spk_0", "spk_1"
    role: Optional[str] = None  # e.g. "doctor", "patient", "nurse", "parent", "interpreter"
    confidence: float = 0.0
    reasoning: str = ""
    embeddings: list[list[float]] = Field(default_factory=list)
    mean_embedding: Optional[list[float]] = None


class SimilarCondition(BaseModel):
    condition_label: str
    similarity_score: float = 0.0


class ImageAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    image_url: str
    clinical_description: str = ""
    similar_conditions: list[SimilarCondition] = Field(default_factory=list)
    soap_section: Optional[str] = None


class LabFlag(str, Enum):
    NORMAL = "normal"
    HIGH = "high"
    LOW = "low"
    CRITICAL = "critical"


class LabResult(BaseModel):
    test: str
    value: float
    unit: str
    reference_range: Optional[str] = None
    flag: LabFlag = LabFlag.NORMAL


class LabReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    image_url: str = ""
    lab_name: str = ""
    date: Optional[str] = None
    results: list[LabResult] = Field(default_factory=list)
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_chunk_id: Optional[str] = None


class FollowUpItem(BaseModel):
    action: str
    type: FollowUpType = FollowUpType.OTHER
    timeframe: Optional[str] = None
    details: Optional[str] = None


class PatientSummary(BaseModel):
    visit_summary: str = ""
    new_medications: list[str] = Field(default_factory=list)
    follow_up_steps: list[str] = Field(default_factory=list)
    when_to_seek_care: str = ""
    reading_level: ReadingLevel = ReadingLevel.MIDDLE_SCHOOL


# --- Session model ---


class Session(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    mode: SessionMode = SessionMode.ACTIVE_VISIT
    visit_type: VisitType = VisitType.IN_PERSON
    patient_context: Optional[PatientContext] = None
    transcript_chunks: list[TranscriptChunk] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)
    interaction_flags: list[InteractionFlag] = Field(default_factory=list)
    clinical_alerts: list[ClinicalAlert] = Field(default_factory=list)
    soap_note: SOAPNote = Field(default_factory=SOAPNote)
    differential: list[str] = Field(default_factory=list)
    image_analyses: list[ImageAnalysis] = Field(default_factory=list)
    lab_reports: list[LabReport] = Field(default_factory=list)
    diagnosis_codes: list[DiagnosisCode] = Field(default_factory=list)
    follow_ups: list[FollowUpItem] = Field(default_factory=list)
    patient_summary: Optional[PatientSummary] = None
    pending_orders: list[str] = Field(default_factory=list)
    speaker_profiles: list[SpeakerProfile] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)  # Pre-loaded from FHIR or detected
    conditions: list[str] = Field(default_factory=list)  # Active problem list from FHIR


class LLMProviderConfig(BaseModel):
    provider: str = "vllm_local"  # ollama, vllm_local, openrouter, vertex_ai, custom
    base_url: str = "http://localhost:8080/v1"
    model: str = "google/medgemma-27b-text-it"
    api_key: str = ""

class ClassifierConfig(BaseModel):
    id: str
    name: str
    type: str  # "audio" or "image"
    model_id: str  # HF repo or local path
    labels: list[str] = Field(default_factory=list)
    enabled: bool = False
    loaded: bool = False  # runtime only, not persisted

class AppSettings(BaseModel):
    llm: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    vision_llm: LLMProviderConfig = Field(default_factory=lambda: LLMProviderConfig(
        base_url="http://localhost:8080/v1",
        model="google/medgemma-1.5-4b-it",
    ))
    classifiers: list[ClassifierConfig] = Field(default_factory=list)


# --- Request / Response helpers ---


class CreateSessionRequest(BaseModel):
    visit_type: VisitType = VisitType.IN_PERSON
    patient_context: Optional[PatientContext] = None
    fhir_patient_id: Optional[str] = None  # If set, auto-import from FHIR server


class SOAPUpdateRequest(BaseModel):
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None


# --- FHIR integration models ---


class FHIRPatient(BaseModel):
    id: str
    name: str
    birth_date: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None


class FHIRAllergy(BaseModel):
    substance: str
    criticality: Optional[str] = None
    reaction: Optional[str] = None


class FHIRImportResult(BaseModel):
    patient: FHIRPatient
    medications: list[Medication] = Field(default_factory=list)
    allergies: list[FHIRAllergy] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
