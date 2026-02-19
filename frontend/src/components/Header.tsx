import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { SessionMode } from "../types";

interface HeaderProps {
  mode?: SessionMode;
  sessionStart?: Date;
  onEnd?: () => void;
  onPause?: () => void;
  isPaused?: boolean;
  isRecording?: boolean;
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function Header({
  mode,
  sessionStart,
  onEnd,
  onPause,
  isPaused = false,
  isRecording = false,
}: HeaderProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!sessionStart || isPaused) return;
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - sessionStart.getTime()) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [sessionStart, isPaused]);

  return (
    <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-6 shadow-sm">
      {/* Left: Logo */}
      <div className="flex items-center gap-3">
        <Link to="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-clinical-600">
            <svg
              className="h-4 w-4 text-white"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
              />
            </svg>
          </div>
          <span className="text-lg font-bold text-slate-900">Scribe</span>
        </Link>

        {mode && (
          <span className="rounded-full bg-clinical-100 px-3 py-0.5 text-xs font-medium text-clinical-700">
            {mode === "active_visit" ? "In-Room" : "Post-Visit Review"}
          </span>
        )}
      </div>

      {/* Center: Recording indicator + timer */}
      {mode === "active_visit" && sessionStart && (
        <div className="flex items-center gap-4">
          {isRecording && !isPaused && (
            <div className="flex items-center gap-2">
              <span className="recording-pulse inline-block h-2.5 w-2.5 rounded-full bg-alert-500" />
              <span className="text-sm font-medium text-alert-600">
                Recording
              </span>
            </div>
          )}
          {isPaused && (
            <div className="flex items-center gap-2">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-warning-500" />
              <span className="text-sm font-medium text-warning-600">
                Paused
              </span>
            </div>
          )}
          <span className="font-mono text-sm text-slate-500">
            {formatElapsed(elapsed)}
          </span>
        </div>
      )}

      {/* Right: Controls */}
      <div className="flex items-center gap-2">
        {mode === "active_visit" && (
          <>
            <button
              onClick={onPause}
              className="btn-secondary !px-4 !py-1.5 text-xs"
            >
              {isPaused ? "Resume" : "Pause"}
            </button>
            <button
              onClick={onEnd}
              className="btn-danger !px-4 !py-1.5 text-xs"
            >
              End Visit
            </button>
          </>
        )}
      </div>
    </header>
  );
}
