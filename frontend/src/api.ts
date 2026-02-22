import type { DiagnosisCode, FollowUpItem, HearAnalysisResult, ImageAnalysis, LabReport, PatientSummary, Session, SessionSummary, SOAPNote, VisitType } from "./types";

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
      },
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

export async function getLlmUsage(): Promise<LlmUsage> {
  return request<LlmUsage>("/llm-usage");
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
