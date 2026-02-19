import { useCallback, useEffect, useRef, useState } from "react";
import { getSessionAudio, analyzeAudioSegment } from "../../api";
import type { HearAnalysisResult } from "../../types";

interface WaveformPlayerProps {
  sessionId: string;
  onAnalysisResult?: (result: HearAnalysisResult) => void;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function WaveformPlayer({
  sessionId,
  onAnalysisResult,
}: WaveformPlayerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [audioBlobUrl, setAudioBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // Selection state
  const [selectionStart, setSelectionStart] = useState<number | null>(null);
  const [selectionEnd, setSelectionEnd] = useState<number | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  // Waveform data (downsampled)
  const waveformRef = useRef<Float32Array | null>(null);

  // Load audio on mount
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        setError(null);
        const blob = await getSessionAudio(sessionId);
        if (cancelled) return;

        const url = URL.createObjectURL(blob);
        setAudioBlobUrl(url);

        const ctx = new AudioContext();
        const arrayBuf = await blob.arrayBuffer();
        const decoded = await ctx.decodeAudioData(arrayBuf);
        if (cancelled) return;

        setDuration(decoded.duration);

        // Downsample for waveform drawing
        const channelData = decoded.getChannelData(0);
        const samples = 800; // canvas width approx
        const blockSize = Math.floor(channelData.length / samples);
        const waveform = new Float32Array(samples);
        for (let i = 0; i < samples; i++) {
          let sum = 0;
          for (let j = 0; j < blockSize; j++) {
            sum += Math.abs(channelData[i * blockSize + j]);
          }
          waveform[i] = sum / blockSize;
        }
        waveformRef.current = waveform;
        ctx.close();
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load audio",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // Cleanup blob URL
  useEffect(() => {
    return () => {
      if (audioBlobUrl) URL.revokeObjectURL(audioBlobUrl);
    };
  }, [audioBlobUrl]);

  // Draw waveform
  const drawWaveform = useCallback(() => {
    const canvas = canvasRef.current;
    const waveform = waveformRef.current;
    if (!canvas || !waveform || duration === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;
    const midY = h / 2;
    const barWidth = w / waveform.length;

    // Clear
    ctx.clearRect(0, 0, w, h);

    // Draw selection highlight
    if (selectionStart !== null && selectionEnd !== null) {
      const x1 = (Math.min(selectionStart, selectionEnd) / duration) * w;
      const x2 = (Math.max(selectionStart, selectionEnd) / duration) * w;
      ctx.fillStyle = "rgba(59, 130, 246, 0.15)";
      ctx.fillRect(x1, 0, x2 - x1, h);
      // Selection borders
      ctx.strokeStyle = "rgba(59, 130, 246, 0.6)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(x1, 0);
      ctx.lineTo(x1, h);
      ctx.moveTo(x2, 0);
      ctx.lineTo(x2, h);
      ctx.stroke();
    }

    // Draw waveform bars
    const maxVal = Math.max(...waveform) || 1;
    for (let i = 0; i < waveform.length; i++) {
      const x = i * barWidth;
      const barH = (waveform[i] / maxVal) * (h * 0.8);

      // Color: played portion = clinical blue, rest = slate
      const time = (i / waveform.length) * duration;
      if (time <= currentTime) {
        ctx.fillStyle = "#2563eb"; // clinical blue
      } else {
        ctx.fillStyle = "#cbd5e1"; // slate-300
      }

      ctx.fillRect(x, midY - barH / 2, Math.max(barWidth - 0.5, 1), barH);
    }

    // Draw playhead
    const playX = (currentTime / duration) * w;
    ctx.strokeStyle = "#1e40af";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(playX, 0);
    ctx.lineTo(playX, h);
    ctx.stroke();
  }, [currentTime, duration, selectionStart, selectionEnd]);

  useEffect(() => {
    drawWaveform();
  }, [drawWaveform]);

  // Update current time during playback
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const handler = () => setCurrentTime(audio.currentTime);
    const endHandler = () => setPlaying(false);
    audio.addEventListener("timeupdate", handler);
    audio.addEventListener("ended", endHandler);
    return () => {
      audio.removeEventListener("timeupdate", handler);
      audio.removeEventListener("ended", endHandler);
    };
  }, [audioBlobUrl]);

  // Canvas mouse handlers for selection
  const getTimeFromX = useCallback(
    (clientX: number) => {
      const canvas = canvasRef.current;
      if (!canvas || duration === 0) return 0;
      const rect = canvas.getBoundingClientRect();
      const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
      return (x / rect.width) * duration;
    },
    [duration],
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      const time = getTimeFromX(e.clientX);
      setSelectionStart(time);
      setSelectionEnd(time);
      setIsDragging(true);
    },
    [getTimeFromX],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging) return;
      const time = getTimeFromX(e.clientX);
      setSelectionEnd(time);
    },
    [isDragging, getTimeFromX],
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Click to seek (if not dragging a selection)
  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      if (
        selectionStart !== null &&
        selectionEnd !== null &&
        Math.abs(selectionEnd - selectionStart) < 0.3
      ) {
        // Single click — seek, clear selection
        const time = getTimeFromX(e.clientX);
        if (audioRef.current) {
          audioRef.current.currentTime = time;
          setCurrentTime(time);
        }
        setSelectionStart(null);
        setSelectionEnd(null);
      }
    },
    [selectionStart, selectionEnd, getTimeFromX],
  );

  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
      setPlaying(false);
    } else {
      audio.play();
      setPlaying(true);
    }
  }, [playing]);

  const handleAnalyze = useCallback(async () => {
    if (selectionStart === null || selectionEnd === null) return;
    const startS = Math.min(selectionStart, selectionEnd);
    const endS = Math.max(selectionStart, selectionEnd);
    if (endS - startS < 0.5) return;

    setAnalyzing(true);
    setAnalysisError(null);
    try {
      const result = await analyzeAudioSegment(sessionId, startS, endS);
      onAnalysisResult?.(result);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "HeAR analysis failed";
      console.error("HeAR analysis failed:", err);
      setAnalysisError(message);
    } finally {
      setAnalyzing(false);
    }
  }, [sessionId, selectionStart, selectionEnd, onAnalysisResult]);

  const hasSelection =
    selectionStart !== null &&
    selectionEnd !== null &&
    Math.abs(selectionEnd - selectionStart) >= 0.5;

  if (loading) {
    return (
      <div className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-6 py-4">
        <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
          <div className="h-3 w-3 animate-spin rounded-full border border-clinical-400 border-t-transparent" />
          Loading visit recording...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-6 py-3">
        <p className="text-xs text-slate-400 dark:text-slate-500">
          No audio recording available
        </p>
      </div>
    );
  }

  return (
    <div className="border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800" ref={containerRef}>
      {audioBlobUrl && (
        <audio ref={audioRef} src={audioBlobUrl} preload="auto" />
      )}

      <div className="flex items-center gap-3 px-4 py-2">
        {/* Play button */}
        <button
          onClick={togglePlay}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-clinical-600 text-white transition-colors hover:bg-clinical-700"
          title={playing ? "Pause" : "Play"}
        >
          {playing ? (
            <svg className="h-3 w-3" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 4h4v16H6zM14 4h4v16h-4z" />
            </svg>
          ) : (
            <svg className="h-3 w-3" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>
          )}
        </button>

        {/* Waveform canvas */}
        <div className="relative min-w-0 flex-1">
          <canvas
            ref={canvasRef}
            className="h-16 w-full cursor-crosshair rounded"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onClick={handleClick}
          />
        </div>

        {/* Time display */}
        <span className="shrink-0 text-xs font-mono text-slate-500 dark:text-slate-400">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>
      </div>

      {/* Selection info bar */}
      {hasSelection && (
        <div className="flex flex-col border-t border-slate-100 dark:border-slate-700 bg-blue-50 dark:bg-blue-900/30">
          <div className="flex items-center gap-2 px-4 py-1.5">
            <span className="text-xs text-blue-700 dark:text-blue-300">
              Selected: {formatTime(Math.min(selectionStart!, selectionEnd!))} -{" "}
              {formatTime(Math.max(selectionStart!, selectionEnd!))}
              {" "}
              ({Math.abs(selectionEnd! - selectionStart!).toFixed(1)}s)
            </span>
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="ml-auto rounded bg-clinical-600 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-clinical-700 disabled:opacity-50"
            >
              {analyzing ? (
                <span className="flex items-center gap-1.5">
                  <span className="h-3 w-3 animate-spin rounded-full border border-white border-t-transparent" />
                  Analyzing...
                </span>
              ) : (
                "Analyze with HeAR"
              )}
            </button>
            <button
              onClick={() => {
                setSelectionStart(null);
                setSelectionEnd(null);
                setAnalysisError(null);
              }}
              className="text-xs text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:text-slate-300"
            >
              Clear
            </button>
          </div>
          {analysisError && (
            <div className="flex items-center gap-2 border-t border-red-100 dark:border-red-800 bg-red-50 dark:bg-red-900/30 px-4 py-1.5">
              <svg className="h-3.5 w-3.5 shrink-0 text-red-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
              </svg>
              <span className="text-xs text-red-700 dark:text-red-300">{analysisError}</span>
              <button
                onClick={() => setAnalysisError(null)}
                className="ml-auto text-xs text-red-400 hover:text-red-600"
              >
                Dismiss
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
