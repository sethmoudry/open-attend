import { useCallback, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Header from "../components/Header";
import EndVisitModal from "../components/EndVisitModal";
import ModeTransitionScreen from "../components/ModeTransitionScreen";
import AlertsSection from "../components/sidebar/AlertsSection";
import SOAPDraftSection from "../components/sidebar/SOAPDraftSection";
import DifferentialSection from "../components/sidebar/DifferentialSection";
import PendingOrdersSection from "../components/sidebar/PendingOrdersSection";
import ImageUploadSection from "../components/sidebar/ImageUploadSection";
import LabUploadSection from "../components/sidebar/LabUploadSection";
import LabResultsSection from "../components/sidebar/LabResultsSection";
import UpdateStatusBar from "../components/sidebar/UpdateStatusBar";
import SpeakerLegend, { getSpeakerColor, resolveRole } from "../components/SpeakerLegend";
import SpeakerRoleSelector from "../components/SpeakerRoleSelector";
import { useSessionPolling } from "../hooks/useSessionPolling";
import { useAudioStream } from "../hooks/useAudioStream";
import { useAudioCapture } from "../hooks/useAudioCapture";
import { useSamplePlayback } from "../hooks/useSamplePlayback";
import { endVisit, finalizeSession, updateSpeakerRoles } from "../api";
import type { LabReport, Speaker, SpeakerProfile, TranscriptChunk } from "../types";

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

const ROLE_LABELS: Record<Speaker, string> = {
  doctor: "Clinician",
  patient: "Patient",
  parent: "Parent",
  nurse: "Nurse",
  interpreter: "Interpreter",
  other: "Other",
  unknown: "Speaker",
};

export default function InRoomLayout() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [sessionStart] = useState(() => new Date());
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);

  // End visit flow state
  const [showEndModal, setShowEndModal] = useState(false);
  const [isEnding, setIsEnding] = useState(false);
  const [showTransition, setShowTransition] = useState(false);
  const [llmUsage, setLlmUsage] = useState<import("../api").LlmUsage | null>(null);

  // Sidebar section collapse state
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({
    alerts: false, soap: false, differential: false,
    orders: false, images: false, labs: false, labResults: false,
  });
  const toggleSection = (key: string) =>
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));

  // Speaker role reassignment
  const [openSpeakerSelector, setOpenSpeakerSelector] = useState<string | null>(null);

  // Session polling -- gets sidebar data every 2s
  const { session, loading: _sessionLoading, mutate } = useSessionPolling({
    sessionId: id ?? "",
    enabled: !!id,
  });

  // WebSocket connection -- receives transcript chunks
  const {
    connected,
    transcriptChunks,
    error: wsError,
    processingStatus,
    sendAudioChunk,
    disconnect,
    connect,
    clearTranscript,
  } = useAudioStream({
    sessionId: id ?? "",
    autoConnect: !!id,
  });

  // Audio capture -- records mic and sends chunks over WS
  const {
    state: recordingState,
    audioLevel,
    chunkCount,
    startRecording,
    pauseRecording,
    resumeRecording,
    stopRecording,
  } = useAudioCapture({
    onChunk: sendAudioChunk,
    onError: (err) => console.error("[AudioCapture]", err.message),
  });

  // Sample playback -- feeds pre-recorded audio through the WS
  const {
    playing: samplePlaying,
    progress: sampleProgress,
    startSample,
    stopSample,
  } = useSamplePlayback({
    sendAudioChunk,
    disconnectStream: disconnect,
    connectStream: connect,
    clearTranscript,
  });

  const isPaused = recordingState === "paused";
  const isRecording = recordingState === "recording";
  const isIdle = recordingState === "idle";

  // Auto-scroll transcript (scoped to transcript container, not the whole panel)
  const transcriptContainerRef = useRef<HTMLDivElement | null>(null);
  const scrollToBottom = useCallback(() => {
    const container = transcriptContainerRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, []);

  const prevChunkCountRef = useRef(0);
  if (transcriptChunks.length > prevChunkCountRef.current) {
    prevChunkCountRef.current = transcriptChunks.length;
    setTimeout(scrollToBottom, 50);
  }

  const handlePause = useCallback(() => {
    if (isRecording) {
      pauseRecording();
    } else if (isPaused) {
      resumeRecording();
    }
  }, [isRecording, isPaused, pauseRecording, resumeRecording]);

  const handleEndClick = () => {
    setShowEndModal(true);
  };

  const handleCancelEnd = () => {
    setShowEndModal(false);
  };

  const handleConfirmEnd = async () => {
    if (!id) return;
    setIsEnding(true);

    try {
      stopRecording();
      stopSample();
      const result = await endVisit(id);
      setLlmUsage(result.llm_usage);
      setShowEndModal(false);
      setShowTransition(true);
      await finalizeSession(id);
    } catch (err) {
      console.error("Failed to end visit:", err);
      setShowEndModal(false);
      setShowTransition(true);
    } finally {
      setIsEnding(false);
    }
  };

  const handleRoleChange = useCallback(
    async (speakerId: string, role: Speaker) => {
      if (!id) return;
      try {
        const updated = await updateSpeakerRoles(id, [
          { speaker_id: speakerId, role },
        ]);
        mutate(updated);
      } catch (err) {
        console.error("Failed to update speaker role:", err);
      }
    },
    [id, mutate],
  );

  const handleTransitionComplete = useCallback(() => {
    navigate(`/session/${id}/review`);
  }, [navigate, id]);

  // Merge WS transcript chunks with polled session transcript, filtering empty text
  const displayChunks: TranscriptChunk[] = (
    transcriptChunks.length > 0
      ? transcriptChunks
      : session?.transcript_chunks ?? []
  ).filter((c) => c.text && c.text.trim().length > 0);

  // Speaker profiles from session
  const speakerProfiles: SpeakerProfile[] = session?.speaker_profiles ?? [];

  // Audio level bars
  const levelBars = 10;
  const activeBars = Math.round(audioLevel * levelBars);

  // Lab report callback -- polling will pick up the new data; this just forces an immediate refresh
  const handleLabReport = useCallback(
    (_report: LabReport) => {
      // Trigger a re-poll so sidebar shows the new report immediately
      if (session) mutate({ ...session });
    },
    [session, mutate],
  );

  // Sidebar data from session
  const alerts = session?.clinical_alerts ?? [];
  const medications = session?.medications ?? [];
  const soapNote = session?.soap_note ?? { subjective: "", objective: "", assessment: "", plan: "", status: "draft" as const, last_updated: "" };
  const differential = session?.differential ?? [];
  const pendingOrders = session?.pending_orders ?? [];
  const imageAnalyses = session?.image_analyses ?? [];
  const labReports = session?.lab_reports ?? [];
  const sessionId = session?.id ?? "";

  // Counts for the end-visit modal summary
  const medicationsFound = medications.length;
  const alertsRaised = alerts.length;

  return (
    <div className="flex h-screen flex-col bg-slate-100 dark:bg-slate-950">
      <Header
        mode="active_visit"
        sessionStart={sessionStart}
        isRecording={isRecording || isPaused}
        isPaused={isPaused}
        isIdle={isIdle}
        onPause={handlePause}
        onEnd={handleEndClick}
        onStartRecording={() => startRecording()}
        onSampleToggle={samplePlaying ? stopSample : startSample}
        samplePlaying={samplePlaying}
      />

      {/* Two-panel layout: SOAP (left) | Sidebar + Transcript (right) */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel: SOAP note only */}
        <div className="scrollbar-thin flex w-1/2 flex-col overflow-y-auto border-r border-slate-200 bg-slate-100 dark:border-slate-700 dark:bg-slate-950">
          <div className="border-b border-slate-200 bg-slate-50 px-6 py-3 dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              SOAP Note
            </h2>
          </div>
          <div className="p-4">
            <SOAPDraftSection
              soapNote={soapNote}
              collapsed={collapsed.soap}
              onToggle={() => toggleSection("soap")}
            />
          </div>
        </div>

        {/* Right panel: Sidebar sections with Transcript */}
        <div className="scrollbar-thin flex w-1/2 flex-col overflow-y-auto bg-slate-100 dark:bg-slate-950">
          <div className="border-b border-slate-200 bg-slate-50 px-6 py-3 dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Agent Sidebar
            </h2>
          </div>

          <div className="space-y-4 p-4">
            {sessionId && (
              <UpdateStatusBar sessionId={sessionId} onUpdated={() => {}} />
            )}
            {/* Pre-loaded Allergies */}
            {(session?.allergies?.length ?? 0) > 0 && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/40">
                <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-400">
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                  </svg>
                  Known Allergies
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {session!.allergies.map((allergy, i) => (
                    <span key={i} className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/60 dark:text-amber-300">
                      {allergy}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <AlertsSection
              alerts={alerts}
              collapsed={collapsed.alerts}
              onToggle={() => toggleSection("alerts")}
            />

            {/* Active Conditions (Problem List) */}
            {(session?.conditions?.length ?? 0) > 0 && (
              <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-700 dark:bg-slate-800">
                <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  <svg className="h-3.5 w-3.5 text-clinical-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25ZM6.75 12h.008v.008H6.75V12Zm0 3h.008v.008H6.75V15Zm0 3h.008v.008H6.75V18Z" />
                  </svg>
                  Active Conditions
                </h3>
                <div className="space-y-1">
                  {session!.conditions.map((condition, i) => (
                    <div key={i} className="rounded bg-slate-50 px-2 py-1 text-xs text-slate-600 dark:bg-slate-900 dark:text-slate-300">
                      {condition}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Live Transcript */}
            <div className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
              <div className="px-4 py-0">
                <div className="flex items-center justify-between">
                  <span className="relative py-3 text-sm font-semibold text-slate-900 dark:text-slate-100">
                    Live Transcript
                    <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full bg-clinical-600" />
                  </span>
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block h-2 w-2 rounded-full ${connected ? "bg-success-500" : "bg-slate-300 dark:bg-slate-600"}`}
                    />
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      {connected ? "Connected" : "Offline"}
                    </span>
                  </div>
                </div>
                {processingStatus === 'processing' && (
                  <div className="flex items-center gap-1.5 pb-2 text-xs text-slate-400 dark:text-slate-500">
                    <div className="h-3 w-3 animate-spin rounded-full border border-clinical-400 border-t-transparent" />
                    Processing audio...
                  </div>
                )}
              </div>

              {/* Speaker Legend */}
              {speakerProfiles.length > 0 && (
                <SpeakerLegend
                  profiles={speakerProfiles}
                  onRoleChange={handleRoleChange}
                />
              )}

              <div ref={transcriptContainerRef} className="max-h-96 overflow-y-auto px-4 py-4">
                {displayChunks.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-8 text-center">
                    {samplePlaying ? (
                      <>
                        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-clinical-100 dark:bg-clinical-900/40">
                          <svg className="h-6 w-6 text-clinical-600 animate-pulse" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19.114 5.636a9 9 0 0 1 0 12.728M16.463 8.288a5.25 5.25 0 0 1 0 7.424M6.75 8.25l4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75Z" />
                          </svg>
                        </div>
                        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Processing sample audio...</p>
                        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">Transcript will appear shortly.</p>
                      </>
                    ) : (
                      <>
                        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-clinical-100 dark:bg-clinical-900/40">
                          <svg className="h-6 w-6 text-clinical-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
                          </svg>
                        </div>
                        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
                          {isIdle
                            ? "Click Record or Sample in the header to begin."
                            : isPaused
                              ? "Recording paused"
                              : "Listening... Speak to begin transcription."}
                        </p>
                        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">Transcript will appear here as the conversation progresses.</p>
                      </>
                    )}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {displayChunks.map((chunk) => {
                      const role = resolveRole(chunk.speaker_id, chunk.speaker, speakerProfiles);
                      const badgeColor = getSpeakerColor(chunk.speaker_id, chunk.speaker, speakerProfiles);
                      const label = ROLE_LABELS[role] ?? "Speaker";
                      const speakerTag = chunk.speaker_id ? `${label} (${chunk.speaker_id})` : label;
                      return (
                        <div key={chunk.id} className="group flex gap-3">
                          <div className="flex flex-shrink-0 flex-col items-end pt-0.5">
                            <span className="font-mono text-[10px] text-slate-400 dark:text-slate-500">
                              {formatTimestamp(chunk.timestamp_start)}
                            </span>
                          </div>
                          <div className="relative flex-1">
                            <button
                              onClick={() => {
                                if (chunk.speaker_id) {
                                  setOpenSpeakerSelector(openSpeakerSelector === chunk.id ? null : chunk.id);
                                }
                              }}
                              className={`mr-1.5 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold uppercase leading-none transition-opacity ${badgeColor} ${
                                chunk.speaker_id ? "cursor-pointer hover:opacity-80" : "cursor-default"
                              }`}
                              title={chunk.speaker_id ? "Click to reassign role" : undefined}
                            >
                              {speakerTag}
                            </button>
                            {openSpeakerSelector === chunk.id && chunk.speaker_id && (
                              <SpeakerRoleSelector
                                speakerId={chunk.speaker_id}
                                currentRole={role}
                                onSelect={(sid, r) => { handleRoleChange(sid, r); setOpenSpeakerSelector(null); }}
                                onClose={() => setOpenSpeakerSelector(null)}
                              />
                            )}
                            <p className="mt-0.5 text-sm leading-relaxed text-slate-700 dark:text-slate-300">{chunk.text}</p>
                          </div>
                        </div>
                      );
                    })}
                    <div ref={transcriptEndRef} />
                  </div>
                )}
              </div>

              {/* Audio level bar */}
              <div className="flex items-center gap-4 border-t border-slate-200 bg-slate-50 px-4 py-2 rounded-b-xl dark:border-slate-700 dark:bg-slate-900">
                <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                  <span>Audio:</span>
                  <div className="flex gap-0.5">
                    {Array.from({ length: levelBars }).map((_, i) => (
                      <div
                        key={i}
                        className={`h-3 w-1.5 rounded-sm transition-colors ${i < activeBars ? "bg-clinical-400" : "bg-slate-200 dark:bg-slate-700"}`}
                      />
                    ))}
                  </div>
                </div>
                <span className="text-xs text-slate-400 dark:text-slate-500">Segments: {chunkCount}</span>
                {samplePlaying && (
                  <div className="ml-2 flex items-center gap-1.5">
                    <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                      <div className="h-full rounded-full bg-clinical-500 transition-all" style={{ width: `${sampleProgress * 100}%` }} />
                    </div>
                    <span className="text-[10px] text-slate-400 dark:text-slate-500">{Math.round(sampleProgress * 100)}%</span>
                  </div>
                )}
                {wsError && <span className="ml-auto text-xs text-alert-500">{wsError}</span>}
              </div>
            </div>

            <DifferentialSection
              differential={differential}
              collapsed={collapsed.differential}
              onToggle={() => toggleSection("differential")}
            />

            <PendingOrdersSection
              orders={pendingOrders}
              collapsed={collapsed.orders}
              onToggle={() => toggleSection("orders")}
            />
            {sessionId && (
              <ImageUploadSection
                sessionId={sessionId}
                imageAnalyses={imageAnalyses}
                collapsed={collapsed.images}
                onToggle={() => toggleSection("images")}
              />
            )}
            {sessionId && (
              <LabUploadSection
                sessionId={sessionId}
                labReports={labReports}
                onLabReport={handleLabReport}
                collapsed={collapsed.labs}
                onToggle={() => toggleSection("labs")}
              />
            )}
            <LabResultsSection
              labReports={labReports}
              collapsed={collapsed.labResults}
              onToggle={() => toggleSection("labResults")}
            />
          </div>
        </div>
      </div>

      {/* End Visit Modal */}
      <EndVisitModal
        isOpen={showEndModal}
        onCancel={handleCancelEnd}
        onConfirm={handleConfirmEnd}
        isLoading={isEnding}
        sessionStart={sessionStart}
        chunksProcessed={chunkCount}
        medicationsFound={medicationsFound}
        alertsRaised={alertsRaised}
      />

      {/* Mode Transition Screen */}
      <ModeTransitionScreen
        isVisible={showTransition}
        onComplete={handleTransitionComplete}
        llmUsage={llmUsage}
      />
    </div>
  );
}
