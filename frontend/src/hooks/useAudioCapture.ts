import { useCallback, useEffect, useRef, useState } from 'react';

export type RecordingState = 'idle' | 'recording' | 'paused';

export interface UseAudioCaptureOptions {
  /** Called with each audio chunk blob (every ~5s) */
  onChunk?: (blob: Blob) => void;
  /** Called on error (permission denied, mic disconnect, etc.) */
  onError?: (error: Error) => void;
  /** Chunk interval in ms (default 5000) */
  chunkIntervalMs?: number;
}

export interface UseAudioCaptureReturn {
  state: RecordingState;
  audioLevel: number;
  elapsedTime: number;
  chunkCount: number;
  startRecording: (deviceId?: string) => Promise<void>;
  pauseRecording: () => void;
  resumeRecording: () => void;
  stopRecording: () => void;
}

export function useAudioCapture(options: UseAudioCaptureOptions = {}): UseAudioCaptureReturn {
  const { onChunk, onError, chunkIntervalMs = 5000 } = options;

  const [state, setState] = useState<RecordingState>('idle');
  const [audioLevel, setAudioLevel] = useState(0);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [chunkCount, setChunkCount] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);
  const pausedElapsedRef = useRef<number>(0);

  // Stable refs for callbacks so MediaRecorder handlers don't go stale
  const onChunkRef = useRef(onChunk);
  onChunkRef.current = onChunk;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  // ---- Audio level metering via AnalyserNode ----
  const startLevelMetering = useCallback((stream: MediaStream) => {
    try {
      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.5;
      source.connect(analyser);

      audioContextRef.current = ctx;
      analyserRef.current = analyser;

      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        analyser.getByteFrequencyData(dataArray);
        // RMS-ish level normalized to 0-1
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i] * dataArray[i];
        }
        const rms = Math.sqrt(sum / dataArray.length) / 255;
        setAudioLevel(rms);
        animFrameRef.current = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      // Non-critical — metering just won't work
    }
  }, []);

  const stopLevelMetering = useCallback(() => {
    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    setAudioLevel(0);
  }, []);

  // ---- Elapsed time ticker ----
  const startTimer = useCallback(() => {
    startTimeRef.current = Date.now();
    timerRef.current = setInterval(() => {
      const running = (Date.now() - startTimeRef.current) / 1000;
      setElapsedTime(pausedElapsedRef.current + running);
    }, 250);
  }, []);

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // ---- Core recording controls ----
  const startRecording = useCallback(async (deviceId?: string) => {
    try {
      const constraints: MediaStreamConstraints = {
        audio: deviceId
          ? { deviceId: { exact: deviceId }, echoCancellation: true, noiseSuppression: true }
          : { echoCancellation: true, noiseSuppression: true },
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;

      // Detect mic disconnect
      stream.getAudioTracks().forEach((track) => {
        track.addEventListener('ended', () => {
          onErrorRef.current?.(new Error('Microphone disconnected'));
          stopRecording();
        });
      });

      // Prefer webm/opus, fall back to whatever the browser supports
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : '';

      const recorder = new MediaRecorder(stream, {
        ...(mimeType ? { mimeType } : {}),
        audioBitsPerSecond: 64000,
      });

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          onChunkRef.current?.(e.data);
          setChunkCount((c) => c + 1);
        }
      };

      recorder.onerror = () => {
        onErrorRef.current?.(new Error('MediaRecorder error'));
      };

      mediaRecorderRef.current = recorder;
      recorder.start(chunkIntervalMs);

      startLevelMetering(stream);
      pausedElapsedRef.current = 0;
      setElapsedTime(0);
      setChunkCount(0);
      startTimer();
      setState('recording');
    } catch (err) {
      const error =
        err instanceof DOMException && err.name === 'NotAllowedError'
          ? new Error('Microphone permission denied')
          : err instanceof Error
            ? err
            : new Error('Failed to start recording');
      onErrorRef.current?.(error);
    }
  }, [chunkIntervalMs, startLevelMetering, startTimer]);

  const pauseRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state === 'recording') {
      recorder.pause();
      pausedElapsedRef.current += (Date.now() - startTimeRef.current) / 1000;
      stopTimer();
      setState('paused');
    }
  }, [stopTimer]);

  const resumeRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state === 'paused') {
      recorder.resume();
      startTimer();
      setState('recording');
    }
  }, [startTimer]);

  const stopRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop();
    }
    mediaRecorderRef.current = null;

    // Kill the mic stream
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    stopTimer();
    stopLevelMetering();
    pausedElapsedRef.current = 0;
    setState('idle');
  }, [stopTimer, stopLevelMetering]);

  // ---- Cleanup on unmount ----
  useEffect(() => {
    return () => {
      const recorder = mediaRecorderRef.current;
      if (recorder && recorder.state !== 'inactive') {
        recorder.stop();
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
      stopTimer();
      stopLevelMetering();
    };
  }, [stopTimer, stopLevelMetering]);

  return {
    state,
    audioLevel,
    elapsedTime,
    chunkCount,
    startRecording,
    pauseRecording,
    resumeRecording,
    stopRecording,
  };
}
