import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useSessionPolling } from "../hooks/useSessionPolling";
import SOAPEditor from "../components/editor/SOAPEditor";
import TranscriptReference from "../components/editor/TranscriptReference";
import WaveformPlayer from "../components/audio/WaveformPlayer";
import HearResultsPanel from "../components/audio/HearResultsPanel";
import ExportBar from "../components/export/ExportBar";
import LabUploadSection from "../components/sidebar/LabUploadSection";
import CodePanel from "../components/codes/CodePanel";
import { exportToFHIR, getLlmUsage } from "../api";
import type { LlmUsage } from "../api";
import type { HearAnalysisResult, LabReport, Session, SOAPNote } from "../types";

type SoapSectionKey = "subjective" | "objective" | "assessment" | "plan";

export default function PostVisitLayout() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { session, loading, error, mutate } = useSessionPolling({
    sessionId: id || "",
    intervalMs: 5000,
    enabled: !!id,
  });

  const [localSoap, setLocalSoap] = useState<SOAPNote | null>(null);
  const [llmUsage, setLlmUsage] = useState<LlmUsage | null>(null);
  const [hearResult, setHearResult] = useState<HearAnalysisResult | null>(null);
  const [showHearModal, setShowHearModal] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState<{ status: string; message: string } | null>(null);

  useEffect(() => {
    if (!id) return;
    getLlmUsage(id)
      .then(setLlmUsage)
      .catch(() => {});
  }, [id]);

  const handleSoapUpdated = useCallback((soap: SOAPNote) => {
    setLocalSoap(soap);
  }, []);

  const handlePinToSection = useCallback(
    (section: SoapSectionKey, text: string) => {
      const appendFn = (window as any).__soapEditorAppend;
      if (appendFn) {
        appendFn(section, text);
      }
    },
    [],
  );

  const handleExportToFHIR = useCallback(async () => {
    if (!id) return;
    setExporting(true);
    setExportResult(null);
    try {
      const result = await exportToFHIR(id);
      setExportResult(result);
    } catch (err) {
      setExportResult({ status: "error", message: String(err) });
    } finally {
      setExporting(false);
    }
  }, [id]);

  const handleSessionUpdated = useCallback(
    (updated: Session) => {
      mutate?.(updated);
    },
    [mutate],
  );

  const handleLabReport = useCallback(
    (_report: LabReport) => {
      // Trigger re-poll so the lab results appear immediately
      if (session) mutate?.({ ...session });
    },
    [session, mutate],
  );

  const currentSoap = localSoap || session?.soap_note;

  // Loading state
  if (loading && !session) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-100 dark:bg-slate-950">
        <div className="text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-clinical-600 border-t-transparent" />
          <p className="text-sm text-slate-500 dark:text-slate-400">Loading session...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error && !session) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-100 dark:bg-slate-950">
        <div className="text-center">
          <p className="mb-2 text-sm font-medium text-red-600 dark:text-red-400">
            Failed to load session
          </p>
          <p className="mb-4 text-xs text-slate-400 dark:text-slate-500">{error}</p>
          <button
            onClick={() => navigate("/")}
            className="btn-secondary text-xs"
          >
            Back to Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-slate-100 dark:bg-slate-950">
      {/* Header */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-slate-50 px-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="flex items-center gap-3">
          <Link to="/dashboard" className="flex items-center gap-2 hover:opacity-80">
            <img src="/icon.png" alt="Open Attend" className="h-8 w-8 rounded-lg" />
            <span className="text-lg font-bold text-slate-900 dark:text-slate-100">Open Attend</span>
          </Link>
          <span className="rounded-full bg-emerald-100 px-3 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300">
            Post-Visit Review
          </span>
          {session?.patient_context && (
            <span className="text-xs text-slate-400 dark:text-slate-500">
              {typeof session.patient_context === "string"
                ? session.patient_context
                : ""}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400 dark:text-slate-500">
            Session {id?.slice(0, 8)}
          </span>
          {session?.soap_note.status === "reviewed" && (
            <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300">
              Approved
            </span>
          )}
        </div>
      </header>

      {/* Main content: two-panel layout */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* Left panel: SOAP Editor + Transcript */}
        <div className="flex w-3/5 flex-col border-r border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
          {/* SOAP Editor takes available space */}
          <div className="min-h-0 flex-1 overflow-y-auto">
            {session && currentSoap && (
              <SOAPEditor
                sessionId={session.id}
                soapNote={currentSoap}
                onSoapUpdated={handleSoapUpdated}
              />
            )}
          </div>

          {/* Audio waveform player for HeAR analysis */}
          {session && (
            <WaveformPlayer
              sessionId={session.id}
              onAnalysisResult={(result) => {
                setHearResult(result);
                setShowHearModal(true);
              }}
            />
          )}

          {/* Transcript reference as collapsible bottom panel */}
          {session && (
            <TranscriptReference
              chunks={session.transcript_chunks}
              onPinToSection={handlePinToSection}
            />
          )}
        </div>

        {/* Right panel: Tools & Outputs */}
        <div className="scrollbar-thin flex w-2/5 flex-col overflow-y-auto bg-slate-100 dark:bg-slate-950">
          <div className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-6 py-3">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Tools & Outputs
            </h2>
          </div>

          <div className="space-y-4 p-4">
            {/* Billing Codes (ICD-10 + CPT) */}
            {session && (
              <CodePanel session={session} onSessionUpdate={handleSessionUpdated} />
            )}

            {/* Medications */}
            <div className="card">
              <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                <svg
                  className="h-4 w-4 text-clinical-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="m20.893 13.393-1.135-1.135a2.252 2.252 0 0 1-.421-.585l-1.08-2.16a.414.414 0 0 0-.663-.107.827.827 0 0 1-.812.21l-1.273-.363a.89.89 0 0 0-.738 1.595l.587.39c.59.395.674 1.23.172 1.732l-.2.2c-.212.212-.33.498-.33.796v.41c0 .409-.11.809-.32 1.158l-1.315 2.191a2.11 2.11 0 0 1-1.81 1.025 1.055 1.055 0 0 1-1.055-1.055v-1.172c0-.92-.56-1.747-1.414-2.089l-.655-.261a2.25 2.25 0 0 1-1.383-2.46l.007-.042a2.25 2.25 0 0 1 .29-.787l.09-.15a2.25 2.25 0 0 1 2.37-1.048l1.178.236a1.125 1.125 0 0 0 1.302-.795l.208-.73a1.125 1.125 0 0 0-.578-1.315l-.665-.332-.091.091a2.25 2.25 0 0 1-1.591.659h-.18a.94.94 0 0 0-.662.274.931.931 0 0 1-1.458-1.137l1.411-2.353a2.25 2.25 0 0 0 .286-.76m11.928 9.869A9 9 0 0 0 8.965 3.525m11.928 9.868A9 9 0 1 1 8.965 3.525"
                  />
                </svg>
                Medications
              </h3>
              {session?.medications?.length ? (
                <div className="space-y-1.5">
                  {session.medications.map((med, i) => (
                    <div
                      key={i}
                      className="rounded bg-slate-50 dark:bg-slate-900 px-2.5 py-1.5"
                    >
                      <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        {med.name}
                      </span>
                      {med.dose && (
                        <span className="ml-1.5 text-xs text-slate-500 dark:text-slate-400">
                          {med.dose}
                        </span>
                      )}
                      {med.frequency && (
                        <span className="ml-1 text-xs text-slate-400 dark:text-slate-500">
                          ({med.frequency})
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="space-y-2">
                  <div>
                    <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
                      Current:
                    </span>
                    <p className="text-xs italic text-slate-400 dark:text-slate-500">
                      No medications recorded
                    </p>
                  </div>
                  <div>
                    <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
                      New:
                    </span>
                    <p className="text-xs italic text-slate-400 dark:text-slate-500">
                      No new prescriptions
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Follow-ups */}
            <div className="card">
              <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                <svg
                  className="h-4 w-4 text-clinical-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5"
                  />
                </svg>
                Follow-Up Plan
              </h3>
              {session?.follow_ups?.length ? (
                <div className="space-y-1.5">
                  {session.follow_ups.map((fu, i) => (
                    <div
                      key={i}
                      className="rounded bg-slate-50 dark:bg-slate-900 px-2.5 py-1.5"
                    >
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-clinical-100 dark:bg-clinical-900/40 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-clinical-700 dark:text-clinical-300">
                          {fu.type}
                        </span>
                        <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                          {fu.action}
                        </span>
                      </div>
                      {fu.timeframe && (
                        <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
                          {fu.timeframe}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 dark:text-slate-500">
                  Follow-up items will be extracted from the Plan.
                </p>
              )}
            </div>

            {/* Lab Reports */}
            {id && (
              <LabUploadSection
                sessionId={id}
                labReports={session?.lab_reports ?? []}
                onLabReport={handleLabReport}
              />
            )}

            {/* HeAR Audio Analysis */}
            <div className="card">
              <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                <svg
                  className="h-4 w-4 text-clinical-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M19.114 5.636a9 9 0 0 1 0 12.728M16.463 8.288a5.25 5.25 0 0 1 0 7.424M6.75 8.25l4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75Z"
                  />
                </svg>
                HeAR Audio Analysis
              </h3>
              <p className="mb-2 text-xs text-slate-400 dark:text-slate-500">
                Google's HeAR foundation model extracts 512-dim health acoustic
                embeddings from respiratory sounds (coughs, wheezes, breaths).
                Select a time range on the waveform player to extract embeddings.
              </p>
              <div className="rounded bg-amber-50 dark:bg-amber-900/20 px-2.5 py-1.5 mb-2">
                <p className="text-[10px] font-medium text-amber-700 dark:text-amber-300">
                  Requires trained classifier heads for clinical use (e.g., TB screening,
                  COPD detection). Embeddings are extracted; classification is not included.
                </p>
              </div>
              {hearResult ? (
                <div>
                  <p className="mb-2 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                    Embeddings extracted — {hearResult.embedding_windows ?? 0} window(s) processed
                  </p>
                  <button
                    onClick={() => setShowHearModal(true)}
                    className="btn-secondary w-full !py-2 text-xs"
                  >
                    View Details
                  </button>
                </div>
              ) : (
                <button
                  className="btn-secondary w-full !py-2 text-xs"
                  disabled
                >
                  Select audio range to analyze
                </button>
              )}
            </div>

            {/* Image Analysis */}
            <div className="card">
              <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                <svg
                  className="h-4 w-4 text-clinical-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0 0 22.5 18.75V5.25A2.25 2.25 0 0 0 20.25 3H3.75A2.25 2.25 0 0 0 1.5 5.25v13.5A2.25 2.25 0 0 0 3.75 21Z"
                  />
                </svg>
                Medical Image Embeddings
              </h3>
              <p className="mb-2 text-xs text-slate-400 dark:text-slate-500">
                MedSigLIP encodes medical images (X-rays, skin lesions, fundus photos)
                into embeddings for similarity search and retrieval.
              </p>
              <div className="rounded bg-amber-50 dark:bg-amber-900/20 px-2.5 py-1.5 mb-2">
                <p className="text-[10px] font-medium text-amber-700 dark:text-amber-300">
                  Requires trained classifier heads for diagnostic use (e.g., chest X-ray
                  triage, retinal screening). Embedding extraction only.
                </p>
              </div>
              <button className="btn-secondary w-full !py-2 text-xs" disabled>
                Upload Image
              </button>
            </div>

            {/* Patient Summary */}
            <div className="card">
              <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                <svg
                  className="h-4 w-4 text-clinical-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z"
                  />
                </svg>
                Patient Summary
              </h3>
              {session?.patient_summary ? (
                <div className="space-y-2 text-xs text-slate-600 dark:text-slate-300">
                  <p>{session.patient_summary.visit_summary}</p>
                </div>
              ) : (
                <div className="flex gap-2">
                  <button className="btn-primary flex-1 !py-2 text-xs">
                    Generate
                  </button>
                  <button
                    className="btn-secondary flex-1 !py-2 text-xs"
                    disabled
                  >
                    Preview
                  </button>
                </div>
              )}
            </div>

            {/* Export to EHR */}
            {session?.patient_context?.fhir_id && (
              <div className="card">
                <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  <svg className="h-4 w-4 text-clinical-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
                  </svg>
                  Export to EHR
                </h3>
                <p className="mb-3 text-xs text-slate-400 dark:text-slate-500">
                  Export SOAP note as a FHIR DocumentReference to the connected EHR.
                </p>
                {exportResult && (
                  <div className={`mb-2 rounded px-2.5 py-1.5 text-xs ${
                    exportResult.status === "success"
                      ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
                      : "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300"
                  }`}>
                    {exportResult.message}
                  </div>
                )}
                <button
                  onClick={handleExportToFHIR}
                  disabled={exporting || session?.soap_note.status !== "reviewed"}
                  title={session?.soap_note.status !== "reviewed" ? "Approve the note before exporting" : "Export to FHIR"}
                  className={`w-full !py-2 text-xs ${
                    session?.soap_note.status !== "reviewed"
                      ? "rounded-lg bg-slate-100 dark:bg-slate-900 text-slate-400 dark:text-slate-500 cursor-not-allowed font-medium"
                      : "btn-primary"
                  }`}
                >
                  {exporting ? "Exporting..." : "Export to FHIR"}
                </button>
                {session?.soap_note.status !== "reviewed" && (
                  <p className="mt-1.5 text-[10px] text-slate-400 dark:text-slate-500">
                    Approve the SOAP note before exporting to EHR.
                  </p>
                )}
              </div>
            )}

            {/* Statistics */}
            <div className="card">
              <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                <svg
                  className="h-4 w-4 text-clinical-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z"
                  />
                </svg>
                Statistics
              </h3>
              <div className="grid grid-cols-2 gap-2">
                {/* Speakers */}
                <div className="rounded bg-slate-50 dark:bg-slate-900 px-2.5 py-2">
                  <p className="text-[10px] font-medium uppercase text-slate-400 dark:text-slate-500">
                    Speakers
                  </p>
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    {session?.speaker_profiles?.length ?? 0}
                  </p>
                </div>
                {/* Conversation Time */}
                <div className="rounded bg-slate-50 dark:bg-slate-900 px-2.5 py-2">
                  <p className="text-[10px] font-medium uppercase text-slate-400 dark:text-slate-500">
                    Conversation Time
                  </p>
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    {(() => {
                      const chunks = session?.transcript_chunks;
                      if (!chunks?.length) return "--";
                      const start = chunks[0].timestamp_start;
                      const end = chunks[chunks.length - 1].timestamp_end;
                      const dur = Math.max(0, end - start);
                      const mins = Math.floor(dur / 60);
                      const secs = Math.round(dur % 60);
                      return `${mins}m ${secs}s`;
                    })()}
                  </p>
                </div>
                {/* Audio Segments */}
                <div className="rounded bg-slate-50 dark:bg-slate-900 px-2.5 py-2">
                  <p className="text-[10px] font-medium uppercase text-slate-400 dark:text-slate-500">
                    Audio Segments
                  </p>
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    {session?.transcript_chunks?.length ?? 0}
                  </p>
                </div>
                {/* LLM Calls */}
                <div className="rounded bg-slate-50 dark:bg-slate-900 px-2.5 py-2">
                  <p className="text-[10px] font-medium uppercase text-slate-400 dark:text-slate-500">
                    LLM Calls
                  </p>
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    {llmUsage?.total_calls ?? "--"}
                  </p>
                </div>
                {/* Total Tokens */}
                <div className="rounded bg-slate-50 dark:bg-slate-900 px-2.5 py-2">
                  <p className="text-[10px] font-medium uppercase text-slate-400 dark:text-slate-500">
                    Total Tokens
                  </p>
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    {llmUsage?.total_tokens?.toLocaleString() ?? "--"}
                  </p>
                </div>
                {/* Estimated Cost */}
                <div className="rounded bg-slate-50 dark:bg-slate-900 px-2.5 py-2">
                  <p className="text-[10px] font-medium uppercase text-slate-400 dark:text-slate-500">
                    Estimated Cost
                  </p>
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    {llmUsage
                      ? `$${llmUsage.estimated_cost_usd.toFixed(4)}`
                      : "--"}
                  </p>
                </div>
                {/* Model */}
                <div className="col-span-2 rounded bg-slate-50 dark:bg-slate-900 px-2.5 py-2">
                  <p className="text-[10px] font-medium uppercase text-slate-400 dark:text-slate-500">
                    Model
                  </p>
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    {llmUsage?.model ?? "--"}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom export bar */}
      {session && (
        <ExportBar
          session={session}
          onSessionUpdated={handleSessionUpdated}
          onDiscard={() => navigate("/")}
        />
      )}

      {/* HeAR Results Modal */}
      {showHearModal && hearResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="relative mx-4 w-full max-w-lg rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-700 px-6 py-4">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-clinical-100 dark:bg-clinical-900/40">
                  <svg
                    className="h-4 w-4 text-clinical-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2}
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M19.114 5.636a9 9 0 0 1 0 12.728M16.463 8.288a5.25 5.25 0 0 1 0 7.424M6.75 8.25l4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75Z"
                    />
                  </svg>
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                    HeAR Audio Analysis
                  </h2>
                  <p className="text-xs text-slate-400 dark:text-slate-500">
                    {hearResult.segment_duration?.toFixed(1)}s segment
                    {hearResult.embedding_windows
                      ? ` — ${hearResult.embedding_windows} embedding window${hearResult.embedding_windows > 1 ? "s" : ""}`
                      : ""}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowHearModal(false)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 dark:text-slate-500 transition-colors hover:bg-slate-100 dark:hover:bg-slate-700 hover:text-slate-600 dark:text-slate-300"
              >
                <svg
                  className="h-5 w-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M6 18 18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            {/* Body */}
            <div className="max-h-[60vh] overflow-y-auto px-6 py-4">
              <HearResultsPanel result={hearResult} />
            </div>

            {/* Footer */}
            <div className="flex justify-end border-t border-slate-200 dark:border-slate-700 px-6 py-3">
              <button
                onClick={() => setShowHearModal(false)}
                className="btn-secondary !py-2 text-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
