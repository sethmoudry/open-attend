import { useCallback, useEffect, useState } from "react";
import { getThrottleStatus, forceUpdate, type ThrottleStatus } from "../../api";

interface UpdateStatusBarProps {
  sessionId: string;
  onUpdated?: () => void;
}

export default function UpdateStatusBar({ sessionId, onUpdated }: UpdateStatusBarProps) {
  const [status, setStatus] = useState<ThrottleStatus | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const s = await getThrottleStatus();
        if (active) setStatus(s);
      } catch {
        /* ignore */
      }
    };
    poll();
    const interval = setInterval(poll, 3000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const handleRefresh = useCallback(async () => {
    if (!sessionId || refreshing) return;
    setRefreshing(true);
    try {
      await forceUpdate(sessionId);
      onUpdated?.();
      // Re-fetch throttle status
      const s = await getThrottleStatus();
      setStatus(s);
    } catch (err) {
      console.error("Force update failed:", err);
    } finally {
      setRefreshing(false);
    }
  }, [sessionId, refreshing, onUpdated]);

  const formatTime = (seconds: number) => {
    if (seconds <= 0) return "Ready";
    if (seconds < 60) return `${Math.ceil(seconds)}s`;
    const m = Math.floor(seconds / 60);
    const s = Math.ceil(seconds % 60);
    return `${m}m ${s}s`;
  };

  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2">
      <div className="flex items-center gap-3 text-[11px] text-slate-500">
        {status ? (
          <>
            <span title="Alerts">
              <span className="font-medium text-slate-400">Alerts</span>{" "}
              {formatTime(status.alerts.seconds_until_due)}
            </span>
            <span className="text-slate-300">|</span>
            <span title="Medications">
              <span className="font-medium text-slate-400">Meds</span>{" "}
              {formatTime(status.medications.seconds_until_due)}
            </span>
            <span className="text-slate-300">|</span>
            <span title="Differential">
              <span className="font-medium text-slate-400">Diff</span>{" "}
              {formatTime(status.differential.seconds_until_due)}
            </span>
          </>
        ) : (
          <span className="text-slate-400">Loading...</span>
        )}
      </div>
      <button
        onClick={handleRefresh}
        disabled={refreshing}
        className="flex items-center gap-1 rounded-md bg-clinical-50 px-2 py-1 text-[11px] font-medium text-clinical-700 transition-colors hover:bg-clinical-100 disabled:opacity-50"
        title="Force refresh all sidebar data now"
      >
        {refreshing ? (
          <svg className="h-3 w-3 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        ) : (
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
          </svg>
        )}
        Refresh
      </button>
    </div>
  );
}
