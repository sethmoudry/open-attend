import type { DiagnosisCode, FHIRImportResult, FHIRPatient, FollowUpItem, HearAnalysisResult, ImageAnalysis, LabReport, Medication, PatientSummary, Session, SessionSummary, SOAPNote, VisitType } from "./types";

const API_BASE = "/api";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, `${res.status}: ${body}`);
  }

  return res.json();
}

// ── Session endpoints ──

export async function createSession(
  visitType: VisitType,
  patientContext: {
    name?: string;
    age?: number;
    chief_complaint?: string;
    fhir_id?: string;
  },
  fhirData?: {
    medications?: Medication[];
    allergies?: string[];
    conditions?: string[];
  },
): Promise<Session> {
  return request<Session>("/session", {
    method: "POST",
    body: JSON.stringify({
      visit_type: visitType,
      patient_context: {
        name: patientContext.name || null,
        age: patientContext.age || null,
        chief_complaint: patientContext.chief_complaint || null,
        fhir_id: patientContext.fhir_id || null,
      },
      medications: fhirData?.medications ?? [],
      allergies: fhirData?.allergies ?? [],
      conditions: fhirData?.conditions ?? [],
    }),
  });
}

export async function getSession(id: string): Promise<Session> {
  return request<Session>(`/session/${id}`);
}

export interface LlmUsage {
  total_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  model: string;
  provider: string;
}

export interface EndVisitResponse {
  session: Session;
  llm_usage: LlmUsage;
}

export async function endVisit(id: string): Promise<EndVisitResponse> {
  return request<EndVisitResponse>(`/session/${id}/end-visit`, {
    method: "POST",
  });
}

export async function finalizeSession(id: string): Promise<Session> {
  return request<Session>(`/session/${id}/finalize`, {
    method: "POST",
  });
}

export async function updateSOAP(
  sessionId: string,
  updates: Partial<Pick<SOAPNote, "subjective" | "objective" | "assessment" | "plan">>,
): Promise<Session> {
  return request<Session>(`/session/${sessionId}/soap`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

// ── Speaker roles ──

export async function updateSpeakerRoles(
  sessionId: string,
  assignments: Array<{ speaker_id: string; role: string }>,
): Promise<Session> {
  return request<Session>(`/session/${sessionId}/speaker-roles`, {
    method: "PATCH",
    body: JSON.stringify({ assignments }),
  });
}

// ── Code extraction ──

export async function extractCodes(sessionId: string): Promise<Session> {
  return request<Session>(`/session/${sessionId}/extract-codes`, {
    method: "POST",
  });
}

export async function updateCodes(
  sessionId: string,
  codes: DiagnosisCode[],
): Promise<Session> {
  return request<Session>(`/session/${sessionId}/codes`, {
    method: "PATCH",
    body: JSON.stringify({ codes }),
  });
}

// ── Patient summary & follow-ups ──

export async function generateSummary(sessionId: string): Promise<Session> {
  return request<Session>(`/session/${sessionId}/generate-summary`, {
    method: "POST",
  });
}

export async function extractFollowUps(sessionId: string): Promise<Session> {
  return request<Session>(`/session/${sessionId}/extract-followups`, {
    method: "POST",
  });
}

export async function updateSummary(
  sessionId: string,
  summary: Partial<PatientSummary>,
): Promise<Session> {
  return request<Session>(`/session/${sessionId}/summary`, {
    method: "PATCH",
    body: JSON.stringify(summary),
  });
}

export async function updateFollowUps(
  sessionId: string,
  followUps: FollowUpItem[],
): Promise<Session> {
  return request<Session>(`/session/${sessionId}/followups`, {
    method: "PATCH",
    body: JSON.stringify({ follow_ups: followUps }),
  });
}

// ── WebSocket for audio streaming ──

export function connectAudioWebSocket(sessionId: string): WebSocket {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  const ws = new WebSocket(`${protocol}//${host}/ws/audio/${sessionId}`);
  return ws;
}

// ── Image upload ──

export async function uploadImage(
  sessionId: string,
  file: File,
): Promise<ImageAnalysis> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/session/${sessionId}/upload-image`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, `${res.status}: ${body}`);
  }

  return res.json();
}

// ── Lab report upload ──

export async function uploadLabReport(
  sessionId: string,
  file: File,
): Promise<LabReport> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/session/${sessionId}/upload-lab-report`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, `${res.status}: ${body}`);
  }

  return res.json();
}

// ── Approve & Export ──

export async function approveSession(sessionId: string): Promise<Session> {
  return request<Session>(`/session/${sessionId}/approve`, {
    method: "POST",
  });
}

export async function downloadSOAPPdf(sessionId: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/session/${sessionId}/export/soap-pdf`);
  if (!res.ok) {
    const body = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, `${res.status}: ${body}`);
  }
  return res.blob();
}

export async function downloadPatientSummaryPdf(sessionId: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/session/${sessionId}/export/patient-summary-pdf`);
  if (!res.ok) {
    const body = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, `${res.status}: ${body}`);
  }
  return res.blob();
}

export async function getSOAPText(sessionId: string): Promise<string> {
  const res = await fetch(`${API_BASE}/session/${sessionId}/export/soap-text`);
  if (!res.ok) {
    const body = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, `${res.status}: ${body}`);
  }
  return res.text();
}

// ── Feedback ──

export async function submitFeedback(
  sessionId: string,
  rating: number,
  comment: string,
): Promise<void> {
  await request<{ status: string }>("/feedback", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, rating, comment }),
  });
}

// ── Sample audio ──

export interface SampleAudioInfo {
  duration: number;
  chunk_seconds: number[];  // per-chunk durations from VAD
  total_chunks: number;
}

export async function getSampleAudioInfo(): Promise<SampleAudioInfo> {
  return request<SampleAudioInfo>("/sample-audio/info");
}

export async function getSampleAudioFull(): Promise<Blob> {
  const res = await fetch(`${API_BASE}/sample-audio/full`);
  if (!res.ok) {
    const body = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, `${res.status}: ${body}`);
  }
  return res.blob();
}

export async function getSampleAudioChunk(index: number): Promise<Blob> {
  const res = await fetch(`${API_BASE}/sample-audio/chunk/${index}`);
  if (!res.ok) {
    const body = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, `${res.status}: ${body}`);
  }
  return res.blob();
}

// ── Throttle status & force update ──

export interface ThrottleStatus {
  alerts: { seconds_until_due: number };
  medications: { seconds_until_due: number };
  differential: { seconds_until_due: number };
}

export async function getThrottleStatus(): Promise<ThrottleStatus> {
  return request<ThrottleStatus>("/throttle-status");
}

export async function forceUpdate(sessionId: string): Promise<void> {
  await request<{ status: string; updated_keys: string[] }>(
    `/session/${sessionId}/force-update`,
    { method: "POST" },
  );
}

// ── Delete session ──

export async function deleteSession(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/session/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, `${res.status}: ${body}`);
  }
}

// ── Sessions list ──

export async function listSessions(): Promise<SessionSummary[]> {
  return request<SessionSummary[]>("/sessions");
}

// ── LLM usage ──

export async function getLlmUsage(sessionId?: string): Promise<LlmUsage> {
  const params = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  return request<LlmUsage>(`/llm-usage${params}`);
}

// ── Health check ──

export async function healthCheck(): Promise<{ status: string }> {
  return request<{ status: string }>("/health");
}

// ── HeAR audio analysis ──

export async function getSessionAudio(sessionId: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/session/${sessionId}/audio`);
  if (!res.ok) {
    const body = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, `${res.status}: ${body}`);
  }
  return res.blob();
}

export async function analyzeAudioSegment(
  sessionId: string,
  startS: number,
  endS: number,
): Promise<HearAnalysisResult> {
  return request<HearAnalysisResult>(`/session/${sessionId}/analyze-audio`, {
    method: "POST",
    body: JSON.stringify({ start_s: startS, end_s: endS }),
  });
}

// ── FHIR endpoints ──

export async function searchFHIRPatients(query: string): Promise<FHIRPatient[]> {
  return request<FHIRPatient[]>(`/fhir/patients?q=${encodeURIComponent(query)}`);
}

export async function importFHIRPatient(patientId: string): Promise<FHIRImportResult> {
  return request<FHIRImportResult>(`/fhir/patient/${encodeURIComponent(patientId)}/import`);
}

export async function getFHIRConfig(): Promise<{ base_url: string }> {
  return request<{ base_url: string }>("/fhir/config");
}

export async function setFHIRConfig(baseUrl: string): Promise<void> {
  await request<void>("/fhir/config", {
    method: "PUT",
    body: JSON.stringify({ base_url: baseUrl }),
  });
}

export async function exportToFHIR(sessionId: string): Promise<{ status: string; message: string }> {
  return request<{ status: string; message: string }>(`/session/${sessionId}/export-fhir`, {
    method: "POST",
  });
}

// ── Settings API ──

export async function getSettings(): Promise<import("./types").AppSettings> {
  return request<import("./types").AppSettings>("/settings");
}

export async function updateSettings(settings: Partial<import("./types").AppSettings>): Promise<{ status: string }> {
  return request<{ status: string }>("/settings", {
    method: "PUT",
    body: JSON.stringify(settings),
  });
}

export async function testLLMConnection(): Promise<import("./types").LLMTestResult> {
  return request<import("./types").LLMTestResult>("/settings/test-llm", {
    method: "POST",
  });
}

export async function getSystemResources(): Promise<import("./types").SystemResources> {
  return request<import("./types").SystemResources>("/settings/resources");
}

export async function getClassifierCatalog(): Promise<import("./types").ClassifierConfig[]> {
  return request<import("./types").ClassifierConfig[]>("/settings/classifiers/catalog");
}
