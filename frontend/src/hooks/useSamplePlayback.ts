import { useCallback, useRef, useState } from "react";
import { getSampleAudioChunk, getSampleAudioFull, getSampleAudioInfo } from "../api";

export interface UseSamplePlaybackOptions {
  sendAudioChunk: (blob: Blob) => void;
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
  const sendRef = useRef(sendAudioChunk);
  sendRef.current = sendAudioChunk;
  const audioCtxRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);

  const stopSample = useCallback(() => {
    abortRef.current = true;
    if (sourceRef.current) {
      try { sourceRef.current.stop(); } catch { /* already stopped */ }
      sourceRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    setPlaying(false);
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
      for (let i = 0; i < info.total_chunks; i++) {
        if (abortRef.current) break;
        setChunkIndex(i + 1);

        const blob = await getSampleAudioChunk(i);
        if (abortRef.current) break;
        sendRef.current(blob);

        // Wait for chunk duration before sending next
        if (i < info.total_chunks - 1) {
          await new Promise((r) => setTimeout(r, info.chunk_seconds * 1000));
        }
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
