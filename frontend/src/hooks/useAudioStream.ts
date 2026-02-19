import { useCallback, useEffect, useRef, useState } from 'react';

export interface TranscriptChunk {
  id: string;
  timestamp_start: number;
  timestamp_end: number;
  speaker: 'doctor' | 'patient' | 'unknown';
  text: string;
  processed: boolean;
}

export interface UseAudioStreamOptions {
  /** Session ID for the WebSocket URL */
  sessionId: string;
  /** Base WebSocket URL (default ws://localhost:8000) */
  wsBaseUrl?: string;
  /** Auto-connect on mount (default true) */
  autoConnect?: boolean;
  /** Max reconnection attempts (default 5) */
  maxReconnectAttempts?: number;
  /** Base delay between reconnect attempts in ms (default 1000, exponential backoff) */
  reconnectDelayMs?: number;
}

export interface UseAudioStreamReturn {
  /** Whether WebSocket is connected */
  connected: boolean;
  /** Transcript chunks received from server */
  transcriptChunks: TranscriptChunk[];
  /** Current error, if any */
  error: string | null;
  /** Send an audio blob over the socket */
  sendAudioChunk: (blob: Blob) => void;
  /** Manually connect */
  connect: () => void;
  /** Manually disconnect */
  disconnect: () => void;
  /** Clear transcript chunks */
  clearTranscript: () => void;
}

export function useAudioStream(options: UseAudioStreamOptions): UseAudioStreamReturn {
  const {
    sessionId,
    wsBaseUrl = 'ws://localhost:8080',
    autoConnect = true,
    maxReconnectAttempts = 5,
    reconnectDelayMs = 1000,
  } = options;

  const [connected, setConnected] = useState(false);
  const [transcriptChunks, setTranscriptChunks] = useState<TranscriptChunk[]>([]);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalCloseRef = useRef(false);

  const wsUrl = `${wsBaseUrl}/session/${sessionId}/audio`;

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    // Don't open if one is already live
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    intentionalCloseRef.current = false;
    setError(null);

    try {
      const ws = new WebSocket(wsUrl);
      ws.binaryType = 'arraybuffer';

      ws.onopen = () => {
        setConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string) as TranscriptChunk;
          setTranscriptChunks((prev) => [...prev, data]);
        } catch {
          // Ignore non-JSON messages
        }
      };

      ws.onerror = () => {
        setError('WebSocket connection error');
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;

        // Reconnect unless we closed on purpose
        if (!intentionalCloseRef.current && reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = reconnectDelayMs * Math.pow(2, reconnectAttemptsRef.current);
          reconnectAttemptsRef.current += 1;
          setError(`Disconnected. Reconnecting in ${Math.round(delay / 1000)}s...`);
          reconnectTimerRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else if (!intentionalCloseRef.current) {
          setError('Connection lost. Max reconnect attempts reached.');
        }
      };

      wsRef.current = ws;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create WebSocket');
    }
  }, [wsUrl, maxReconnectAttempts, reconnectDelayMs]);

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    clearReconnectTimer();
    reconnectAttemptsRef.current = 0;
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, [clearReconnectTimer]);

  const sendAudioChunk = useCallback((blob: Blob) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      return;
    }
    // Send raw binary
    blob.arrayBuffer().then((buffer) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(buffer);
      }
    });
  }, []);

  const clearTranscript = useCallback(() => {
    setTranscriptChunks([]);
  }, []);

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (autoConnect && sessionId) {
      connect();
    }
    return () => {
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  return {
    connected,
    transcriptChunks,
    error,
    sendAudioChunk,
    connect,
    disconnect,
    clearTranscript,
  };
}
