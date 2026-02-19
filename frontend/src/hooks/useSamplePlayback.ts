import { useCallback, useRef, useState } from "react";
import { getSampleAudioChunk, getSampleAudioFull, getSampleAudioInfo } from "../api";

export interface UseSamplePlaybackOptions {
  sendAudioChunk: (blob: Blob) => void;
  disconnectStream?: () => void;
  connectStream?: () => void;
  clearTranscript?: () => void;
}

export interface UseSamplePlaybackReturn {
  playing: boolean;
  progress: number;
  chunkIndex: number;
  totalChunks: number;
  startSample: () => void;
  stopSample: () => void;
}

export function useSamplePlayback(
  options: UseSamplePlaybackOptions,
): UseSamplePlaybackReturn {
  const { sendAudioChunk } = options;

  const [playing, setPlaying] = useState(false);
  const [chunkIndex, setChunkIndex] = useState(0);
  const [totalChunks, setTotalChunks] = useState(0);

  const abortRef = useRef(false);
  const abortResolveRef = useRef<(() => void) | null>(null);
  const sendRef = useRef(sendAudioChunk);
  sendRef.current = sendAudioChunk;
  const disconnectRef = useRef(options.disconnectStream);
  disconnectRef.current = options.disconnectStream;
  const connectRef = useRef(options.connectStream);
  connectRef.current = options.connectStream;
  const clearRef = useRef(options.clearTranscript);
  clearRef.current = options.clearTranscript;
  const audioCtxRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);

  const stopSample = useCallback(() => {
    abortRef.current = true;
    // Wake up any pending sleep so the loop exits immediately
    if (abortResolveRef.current) {
      abortResolveRef.current();
      abortResolveRef.current = null;
    }
    if (sourceRef.current) {
      try { sourceRef.current.stop(); } catch { /* already stopped */ }
      sourceRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    setPlaying(false);
    clearRef.current?.();
    disconnectRef.current?.();
    setTimeout(() => connectRef.current?.(), 500);
  }, []);

  const startSample = useCallback(async () => {
    abortRef.current = false;
    setPlaying(true);
    setChunkIndex(0);

    try {
      // Fetch info + full audio for playback in parallel
      const [info, fullBlob] = await Promise.all([
        getSampleAudioInfo(),
        getSampleAudioFull(),
      ]);
      if (abortRef.current) return;
      setTotalChunks(info.total_chunks);

      // Start browser audio playback from the full file
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      const arrayBuf = await fullBlob.arrayBuffer();
      const audioBuffer = await ctx.decodeAudioData(arrayBuf);

      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(ctx.destination);
      sourceRef.current = source;
      source.start();

      // Send chunks to server in sync with playback
      const playbackStart = Date.now();
      let cumStart = 0;

      for (let i = 0; i < info.total_chunks; i++) {
        if (abortRef.current) break;
        setChunkIndex(i + 1);

        const chunkDur = info.chunk_seconds[i] ?? 5;
        // Wait until 70% through this chunk's audio before sending
        const targetMs = (cumStart + chunkDur * 0.7) * 1000;
        const elapsed = Date.now() - playbackStart;
        const waitMs = Math.max(0, targetMs - elapsed);

        if (waitMs > 0) {
          await new Promise<void>((resolve) => {
            abortResolveRef.current = resolve;
            setTimeout(() => { abortResolveRef.current = null; resolve(); }, waitMs);
          });
        }
        if (abortRef.current) break;

        const blob = await getSampleAudioChunk(i);
        if (abortRef.current) break;
        sendRef.current(blob);

        cumStart += chunkDur;
      }
    } catch (err) {
      console.error("[SamplePlayback]", err);
    } finally {
      if (sourceRef.current) {
        try { sourceRef.current.stop(); } catch { /* done */ }
        sourceRef.current = null;
      }
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => {});
        audioCtxRef.current = null;
      }
      setPlaying(false);
    }
  }, []);

  const progress = totalChunks > 0 ? chunkIndex / totalChunks : 0;

  return { playing, progress, chunkIndex, totalChunks, startSample, stopSample };
}
