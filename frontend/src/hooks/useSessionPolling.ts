import { useCallback, useEffect, useRef, useState } from "react";
import { getSession } from "../api";
import type { Session } from "../types";

export interface UseSessionPollingOptions {
  sessionId: string;
  /** Polling interval in ms (default 2000) */
  intervalMs?: number;
  /** Whether polling is enabled (default true) */
  enabled?: boolean;
}

export interface UseSessionPollingReturn {
  session: Session | null;
  loading: boolean;
  error: string | null;
  /** Manually update the session state (e.g. after an approve call). */
  mutate: (session: Session) => void;
}

export function useSessionPolling(
  options: UseSessionPollingOptions,
): UseSessionPollingReturn {
  const { sessionId, intervalMs = 2000, enabled = true } = options;

  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback((updated: Session) => {
    setSession(updated);
  }, []);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stoppedRef = useRef(false);

  useEffect(() => {
    if (!sessionId || !enabled) return;

    stoppedRef.current = false;

    const fetchSession = async () => {
      try {
        const data = await getSession(sessionId);
        if (stoppedRef.current) return;
        setSession(data);
        setError(null);
        setLoading(false);

        // Stop polling once we transition to post_visit
        if (data.mode === "post_visit") {
          if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
          }
        }
      } catch (err) {
        if (stoppedRef.current) return;
        setError(
          err instanceof Error ? err.message : "Failed to fetch session",
        );
        setLoading(false);
      }
    };

    // Initial fetch
    fetchSession();

    // Start polling
    timerRef.current = setInterval(fetchSession, intervalMs);

    return () => {
      stoppedRef.current = true;
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [sessionId, intervalMs, enabled]);

  return { session, loading, error, mutate };
}
