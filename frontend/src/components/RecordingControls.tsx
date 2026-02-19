import React, { useCallback } from 'react';
import { useAudioCapture } from '../hooks/useAudioCapture';
import { useAudioStream } from '../hooks/useAudioStream';

interface RecordingControlsProps {
  sessionId: string;
  onEnd?: () => void;
  /** Optional device ID from AudioDeviceSelector */
  deviceId?: string;
  /** Expose transcript chunks to parent — passed through from useAudioStream */
  onTranscriptUpdate?: (chunks: import('../hooks/useAudioStream').TranscriptChunk[]) => void;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export const RecordingControls: React.FC<RecordingControlsProps> = ({
  sessionId,
  onEnd,
  deviceId,
  onTranscriptUpdate,
}) => {
  const { connected, transcriptChunks, error: wsError, sendAudioChunk } = useAudioStream({
    sessionId,
  });

  // Forward transcript chunks to parent whenever they update
  React.useEffect(() => {
    onTranscriptUpdate?.(transcriptChunks);
  }, [transcriptChunks, onTranscriptUpdate]);

  const {
    state,
    audioLevel,
    elapsedTime,
    chunkCount,
    startRecording,
    pauseRecording,
    resumeRecording,
    stopRecording,
  } = useAudioCapture({
    onChunk: sendAudioChunk,
    onError: (err) => console.error('[AudioCapture]', err.message),
  });

  const handleMainButton = useCallback(() => {
    switch (state) {
      case 'idle':
        startRecording(deviceId);
        break;
      case 'recording':
        pauseRecording();
        break;
      case 'paused':
        resumeRecording();
        break;
    }
  }, [state, deviceId, startRecording, pauseRecording, resumeRecording]);

  const handleStop = useCallback(() => {
    stopRecording();
    onEnd?.();
  }, [stopRecording, onEnd]);

  return (
    <div className="flex flex-col gap-4 rounded-2xl bg-gray-900 p-6 shadow-lg">
      {/* Status row */}
      <div className="flex items-center justify-between text-sm text-gray-400">
        <div className="flex items-center gap-2">
          {/* Pulsing red dot when recording */}
          {state === 'recording' && (
            <span className="relative flex h-3 w-3">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
              <span className="relative inline-flex h-3 w-3 rounded-full bg-red-500" />
            </span>
          )}
          {state === 'paused' && <span className="inline-flex h-3 w-3 rounded-full bg-yellow-500" />}
          {state === 'idle' && <span className="inline-flex h-3 w-3 rounded-full bg-gray-600" />}
          <span className="font-medium uppercase tracking-wide">
            {state === 'idle' ? 'Ready' : state === 'recording' ? 'Recording' : 'Paused'}
          </span>
        </div>

        {/* Connection indicator */}
        <div className="flex items-center gap-1.5">
          <span className={`inline-block h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-gray-600'}`} />
          <span>{connected ? 'Connected' : 'Offline'}</span>
        </div>
      </div>

      {/* Audio level meter */}
      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-800">
        <div
          className="h-full rounded-full bg-gradient-to-r from-green-500 via-yellow-400 to-red-500 transition-all duration-75"
          style={{ width: `${Math.min(audioLevel * 100, 100)}%` }}
        />
      </div>

      {/* Time + segments */}
      <div className="flex items-center justify-between text-gray-300">
        <span className="font-mono text-2xl font-bold tabular-nums">{formatTime(elapsedTime)}</span>
        <span className="text-sm text-gray-500">{chunkCount} segments sent</span>
      </div>

      {/* Buttons */}
      <div className="flex items-center justify-center gap-4">
        {/* Main record / pause / resume button */}
        <button
          onClick={handleMainButton}
          className={`flex h-16 w-16 items-center justify-center rounded-full text-white shadow-md transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 ${
            state === 'idle'
              ? 'bg-red-600 hover:bg-red-500 focus:ring-red-500'
              : state === 'recording'
                ? 'bg-yellow-600 hover:bg-yellow-500 focus:ring-yellow-500'
                : 'bg-green-600 hover:bg-green-500 focus:ring-green-500'
          }`}
          aria-label={state === 'idle' ? 'Start recording' : state === 'recording' ? 'Pause recording' : 'Resume recording'}
        >
          {state === 'idle' && (
            /* Mic icon */
            <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 14a3 3 0 003-3V5a3 3 0 10-6 0v6a3 3 0 003 3z" />
              <path d="M17 11a1 1 0 10-2 0 3 3 0 11-6 0 1 1 0 10-2 0 5 5 0 005 5v2H9a1 1 0 100 2h6a1 1 0 100-2h-3v-2a5 5 0 005-5z" />
            </svg>
          )}
          {state === 'recording' && (
            /* Pause icon */
            <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7" viewBox="0 0 24 24" fill="currentColor">
              <path fillRule="evenodd" d="M6.75 5.25a.75.75 0 01.75.75v12a.75.75 0 01-1.5 0V6a.75.75 0 01.75-.75zm10.5 0a.75.75 0 01.75.75v12a.75.75 0 01-1.5 0V6a.75.75 0 01.75-.75z" clipRule="evenodd" />
            </svg>
          )}
          {state === 'paused' && (
            /* Play / resume icon */
            <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7" viewBox="0 0 24 24" fill="currentColor">
              <path fillRule="evenodd" d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.348c1.295.712 1.295 2.573 0 3.285L7.28 19.991c-1.25.687-2.779-.217-2.779-1.643V5.653z" clipRule="evenodd" />
            </svg>
          )}
        </button>

        {/* Stop / End Visit button — only visible when not idle */}
        {state !== 'idle' && (
          <button
            onClick={handleStop}
            className="flex h-12 items-center gap-2 rounded-xl bg-gray-700 px-5 text-sm font-semibold text-white transition-colors hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:ring-offset-gray-900"
            aria-label="End visit"
          >
            {/* Stop square icon */}
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
              <path fillRule="evenodd" d="M4.5 7.5a3 3 0 013-3h9a3 3 0 013 3v9a3 3 0 01-3 3h-9a3 3 0 01-3-3v-9z" clipRule="evenodd" />
            </svg>
            End Visit
          </button>
        )}
      </div>

      {/* Error display */}
      {wsError && <p className="text-center text-xs text-red-400">{wsError}</p>}
    </div>
  );
};

export default RecordingControls;
