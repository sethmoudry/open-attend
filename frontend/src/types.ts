// ── Data objects matching backend models ──

export type Speaker = 'doctor' | 'patient' | 'unknown' | 'other' | 'parent' | 'nurse' | 'interpreter';

export interface TranscriptChunk {
  id: string;
  timestamp_start: number;
  timestamp_end: number;
  speaker: Speaker;
  speaker_id?: string;
  text: string;
  processed: boolean;
}

export interface SpeakerProfile {
  consistent_id: string;
  role: Speaker | null;
}

export interface Medication {
  name: string;
  dose: string | null;
  frequency: string | null;
  source: "patient_reported" | "prescribed";
  chunk_id: string;
}

export interface InteractionFlag {
  drug_a: string;
  drug_b: string;
  severity: "high" | "moderate" | "low" | "none";
  mechanism: string;
  recommendation: string;
}

export type AlertType = "allergy" | "red_flag" | "screening_prompt" | "guideline";
export type AlertPriority = "urgent" | "info";

export interface ClinicalAlert {
  type: AlertType;
  message: string;
  source_chunk_id: string;
  priority: AlertPriority;
  timestamp: string;
}

export type SOAPStatus = "draft" | "in_progress" | "complete" | "reviewed";

export interface SOAPNote {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
  status: SOAPStatus;
  last_updated: string;
}

export interface DiagnosisCode {
  code: string;
  description: string;
  confidence: number;
  source_section: "assessment" | "plan";
  confirmed: boolean;
}

export interface SimilarCondition {
  condition_label: string;
  similarity_score: number;
  reference_image_url: string;
}

export interface ImageAnalysis {
  id: string;
  image_url: string;
  clinical_description: string;
  similar_conditions: SimilarCondition[];
  soap_section: "objective" | null;
}

export type LabFlag = 'normal' | 'high' | 'low' | 'critical';

export interface LabResult {
  test: string;
  value: number;
  unit: string;
  reference_range: string | null;
  flag: LabFlag;
}

export interface LabReport {
  id: string;
  image_url: string;
  lab_name: string;
  date: string | null;
  results: LabResult[];
  uploaded_at: string;
  source_chunk_id: string | null;
}

export type FollowUpType = "lab" | "imaging" | "referral" | "medication" | "appointment" | "other";

export interface FollowUpItem {
  action: string;
  type: FollowUpType;
  timeframe: string;
  details: string;
}

export interface PatientSummary {
  visit_summary: string;
  new_medications: string[];
  follow_up_steps: string[];
  when_to_seek_care: string;
  reading_level: string;
}

export interface PendingOrder {
  name: string;
  cpt_code: string;
  indication: string;
}

export interface PatientContext {
  name: string | null;
  age: number | null;
  chief_complaint: string | null;
  fhir_id?: string;
}

export type SessionMode = "active_visit" | "post_visit";
export type VisitType = "in_person" | "telehealth" | "follow_up" | "new_patient" | "urgent";

export interface Session {
  id: string;
  created_at: string;
  mode: SessionMode;
  visit_type: VisitType;
  patient_context: PatientContext;
  transcript_chunks: TranscriptChunk[];
  speaker_profiles?: SpeakerProfile[];
  medications: Medication[];
  interaction_flags: InteractionFlag[];
  clinical_alerts: ClinicalAlert[];
  soap_note: SOAPNote;
  differential: string[];
  image_analyses: ImageAnalysis[];
  lab_reports: LabReport[];
  diagnosis_codes: DiagnosisCode[];
  follow_ups: FollowUpItem[];
  patient_summary: PatientSummary | null;
  pending_orders: PendingOrder[];
  allergies: string[];
  conditions: string[];
}

// ── FHIR types ──

export interface FHIRPatient {
  id: string;
  name: string;
  birth_date: string | null;
  age: number | null;
  gender: string | null;
}

export interface FHIRAllergy {
  substance: string;
  criticality: string | null;
  reaction: string | null;
}

export interface FHIRImportResult {
  patient: FHIRPatient;
  medications: Medication[];
  allergies: FHIRAllergy[];
  conditions: string[];
}

export interface SessionSummary {
  id: string;
  created_at: string;
  mode: SessionMode;
  visit_type: VisitType;
  patient_context: PatientContext;
  transcript_chunk_count: number;
}

// HeAR audio analysis
export interface DetectedSound {
  sound: string;
  confidence: number;
  description: string;
}

export interface AudioFeatures {
  rms_level: number;
  peak_amplitude: number;
  zero_crossing_rate: number;
  spectral_centroid_hz: number;
  energy_variance: number;
  duration_s: number;
}

export interface HearAnalysisResult {
  detected_sounds: DetectedSound[];
  clinical_relevance: string;
  recommendation: string;
  segment_duration: number;
  audio_features?: AudioFeatures;
  hear_model_used: boolean;
  embedding_windows?: number;
}

// ── Settings types ──

export type LLMProvider = "ollama" | "vllm_local" | "openrouter" | "vertex_ai" | "custom";

export interface LLMProviderConfig {
  provider: LLMProvider;
  base_url: string;
  model: string;
  api_key: string;
}

export interface ClassifierConfig {
  id: string;
  name: string;
  type: "audio" | "image";
  model_id: string;
  labels: string[];
  enabled: boolean;
  installed: boolean;
  description: string;
}

export interface AppSettings {
  llm: LLMProviderConfig;
  vision_llm: LLMProviderConfig;
  classifiers: ClassifierConfig[];
}

export interface SystemResources {
  cpu_percent: number;
  ram: { total_gb: number; used_gb: number; percent: number };
  disk: { total_gb: number; free_gb: number };
  gpu: { name: string; vram_total_gb: number; vram_used_gb: number } | null;
  loaded_models: string[];
}

export interface LLMTestResult {
  status: "ok" | "error";
  latency_ms: number;
  model: string;
  base_url: string;
  error?: string;
  response_preview?: string;
}
