import { useCallback, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Header from "../components/Header";
import EndVisitModal from "../components/EndVisitModal";
import ModeTransitionScreen from "../components/ModeTransitionScreen";
import AgentSidebar from "../components/sidebar/AgentSidebar";
import NotesPanel from "../components/NotesPanel";
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
  const [activeTab, setActiveTab] = useState<'transcript' | 'notes'>('transcript');
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);

  // End visit flow state
  const [showEndModal, setShowEndModal] = useState(false);
  const [isEnding, setIsEnding] = useState(false);
  const [showTransition, setShowTransition] = useState(false);
  const [llmUsage, setLlmUsage] = useState<import("../api").LlmUsage | null>(null);

  // Speaker role reassignment
  const [openSpeakerSelector, setOpenSpeakerSelector] = useState<string | null>(null);

  // Session polling -- gets sidebar data every 2s
  const { session, loading: sessionLoading, mutate } = useSessionPolling({
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

  // Auto-scroll transcript
  const scrollToBottom = useCallback(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
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

  // Counts for the end-visit modal summary
  const medicationsFound = session?.medications?.length ?? 0;
  const alertsRaised = session?.clinical_alerts?.length ?? 0;

  return (
    <div className="flex h-screen flex-col bg-slate-50">
      <Header
        mode="active_visit"
        sessionStart={sessionStart}
        isRecording={isRecording || isPaused}
        isPaused={isPaused}
        onPause={handlePause}
        onEnd={handleEndClick}
      />

      {/* Two-panel layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel: Transcript */}
        <div className="flex w-1/2 flex-col border-r border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-6 py-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <button
                  onClick={() => setActiveTab('transcript')}
                  className={`relative py-3 text-sm transition-colors ${
                    activeTab === 'transcript'
                      ? 'font-semibold text-slate-900'
                      : 'font-medium text-slate-400 hover:text-slate-600'
                  }`}
                >
                  Live Transcript
                  {activeTab === 'transcript' && (
                    <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full bg-clinical-600" />
                  )}
                </button>
                <button
                  onClick={() => setActiveTab('notes')}
                  className={`relative py-3 text-sm transition-colors ${
                    activeTab === 'notes'
                      ? 'font-semibold text-slate-900'
                      : 'font-medium text-slate-400 hover:text-slate-600'
                  }`}
                >
                  Notes
                  {activeTab === 'notes' && (
                    <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full bg-clinical-600" />
                  )}
                </button>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${connected ? "bg-success-500" : "bg-slate-300"}`}
                />
                <span className="text-xs text-slate-500">
                  {connected ? "Connected" : "Offline"}
                </span>
              </div>
            </div>
            {processingStatus === 'processing' && (
              <div className="flex items-center gap-1.5 pb-2 text-xs text-slate-400">
                <div className="h-3 w-3 animate-spin rounded-full border border-clinical-400 border-t-transparent" />
                Processing audio...
              </div>
            )}
          </div>

          {activeTab === 'transcript' ? (
            <>
              {/* Speaker Legend */}
              {speakerProfiles.length > 0 && (
                <SpeakerLegend
                  profiles={speakerProfiles}
                  onRoleChange={handleRoleChange}
                />
              )}

              <div className="scrollbar-thin flex-1 overflow-y-auto px-6 py-4">
                {displayChunks.length === 0 ? (
                  /* Empty state */
                  <div className="flex flex-col items-center justify-center py-20 text-center">
                    {samplePlaying ? (
                      <>
                        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-clinical-100">
                          <svg className="h-6 w-6 text-clinical-600 animate-pulse" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19.114 5.636a9 9 0 0 1 0 12.728M16.463 8.288a5.25 5.25 0 0 1 0 7.424M6.75 8.25l4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75Z" />
                          </svg>
                        </div>
                        <p className="text-sm font-medium text-slate-500">
                          Processing sample audio...
                        </p>
                        <p className="mt-1 text-xs text-slate-400">
                          Transcript will appear shortly.
                        </p>
                      </>
                    ) : (
                      <>
                        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-clinical-100">
                          <svg
                            className="h-6 w-6 text-clinical-600"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={2}
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z"
                            />
                          </svg>
                        </div>
                        <p className="text-sm font-medium text-slate-500">
                          {isIdle
                            ? "Click record to begin capturing audio."
                            : isPaused
                              ? "Recording paused"
                              : "Listening... Speak to begin transcription."}
                        </p>
                        <p className="mt-1 text-xs text-slate-400">
                          Transcript will appear here as the conversation progresses.
                        </p>

                        {isIdle && (
                          <button
                            onClick={() => startRecording()}
                            className="mt-6 flex items-center gap-2 rounded-lg bg-clinical-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-clinical-700"
                          >
                            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M12 14a3 3 0 003-3V5a3 3 0 10-6 0v6a3 3 0 003 3z" />
                              <path d="M17 11a1 1 0 10-2 0 3 3 0 11-6 0 1 1 0 10-2 0 5 5 0 005 5v2H9a1 1 0 100 2h6a1 1 0 100-2h-3v-2a5 5 0 005-5z" />
                            </svg>
                            Start Recording
                          </button>
                        )}
                      </>
                    )}
                  </div>
                ) : (
                  /* Transcript content */
                  <div className="space-y-3">
                    {displayChunks.map((chunk) => {
                      const role = resolveRole(
                        chunk.speaker_id,
                        chunk.speaker,
                        speakerProfiles,
                      );
                      const badgeColor = getSpeakerColor(
                        chunk.speaker_id,
                        chunk.speaker,
                        speakerProfiles,
                      );
                      const label = ROLE_LABELS[role] ?? "Speaker";
                      const speakerTag = chunk.speaker_id
                        ? `${label} (${chunk.speaker_id})`
                        : label;

                      return (
                        <div key={chunk.id} className="group flex gap-3">
                          <div className="flex flex-shrink-0 flex-col items-end pt-0.5">
                            <span className="font-mono text-[10px] text-slate-400">
                              {formatTimestamp(chunk.timestamp_start)}
                            </span>
                          </div>
                          <div className="relative flex-1">
                            <button
                              onClick={() => {
                                if (chunk.speaker_id) {
                                  setOpenSpeakerSelector(
                                    openSpeakerSelector === chunk.id
                                      ? null
                                      : chunk.id,
                                  );
                                }
                              }}
                              className={`mr-1.5 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold uppercase leading-none transition-opacity ${badgeColor} ${
                                chunk.speaker_id
                                  ? "cursor-pointer hover:opacity-80"
                                  : "cursor-default"
                              }`}
                              title={
                                chunk.speaker_id
                                  ? "Click to reassign role"
                                  : undefined
                              }
                            >
                              {speakerTag}
                            </button>
                            {openSpeakerSelector === chunk.id &&
                              chunk.speaker_id && (
                                <SpeakerRoleSelector
                                  speakerId={chunk.speaker_id}
                                  currentRole={role}
                                  onSelect={(sid, r) => {
                                    handleRoleChange(sid, r);
                                    setOpenSpeakerSelector(null);
                                  }}
                                  onClose={() => setOpenSpeakerSelector(null)}
                                />
                              )}
                            <p className="mt-0.5 text-sm leading-relaxed text-slate-700">
                              {chunk.text}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                    <div ref={transcriptEndRef} />
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="scrollbar-thin flex-1 overflow-y-auto">
              <NotesPanel session={session} />
            </div>
          )}

          {/* Audio level bar */}
          <div className="flex items-center gap-4 border-t border-slate-200 bg-slate-50 px-6 py-2.5">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span>Audio Level:</span>
              <div className="flex gap-0.5">
                {Array.from({ length: levelBars }).map((_, i) => (
                  <div
                    key={i}
                    className={`h-3 w-1.5 rounded-sm transition-colors ${
                      i < activeBars ? "bg-clinical-400" : "bg-slate-200"
                    }`}
                  />
                ))}
              </div>
            </div>
            <span className="text-xs text-slate-400">
              Chunks processed: {chunkCount}
            </span>
            <button
              onClick={samplePlaying ? stopSample : startSample}
              disabled={isRecording || isPaused}
              className={`ml-2 flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                samplePlaying
                  ? "bg-alert-100 text-alert-700 hover:bg-alert-200"
                  : "bg-clinical-100 text-clinical-700 hover:bg-clinical-200"
              } disabled:cursor-not-allowed disabled:opacity-40`}
              title={isRecording ? "Stop mic recording first" : samplePlaying ? "Stop sample playback" : "Play a sample doctor-patient conversation"}
            >
              {samplePlaying ? (
                <>
                  <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 24 24">
                    <rect x="6" y="5" width="4" height="14" rx="1" />
                    <rect x="14" y="5" width="4" height="14" rx="1" />
                  </svg>
                  Stop Sample
                </>
              ) : (
                <>
                  <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                  Play Sample
                </>
              )}
            </button>
            {samplePlaying && (
              <div className="ml-2 flex items-center gap-1.5">
                <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200">
                  <div
                    className="h-full rounded-full bg-clinical-500 transition-all"
                    style={{ width: `${sampleProgress * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-slate-400">{Math.round(sampleProgress * 100)}%</span>
              </div>
            )}
            {wsError && (
              <span className="ml-auto text-xs text-alert-500">{wsError}</span>
            )}
          </div>
        </div>

        {/* Right panel: Agent Sidebar */}
        <div className="scrollbar-thin flex w-1/2 flex-col overflow-y-auto bg-slate-50">
          <div className="border-b border-slate-200 bg-white px-6 py-3">
            <h2 className="text-sm font-semibold text-slate-900">
              Agent Sidebar
            </h2>
          </div>

          <AgentSidebar session={session} loading={sessionLoading} onLabReport={handleLabReport} />
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
