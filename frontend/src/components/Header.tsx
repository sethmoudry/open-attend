import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTheme } from "../ThemeContext";
import type { SessionMode } from "../types";

interface HeaderProps {
  mode?: SessionMode;
  sessionStart?: Date;
  onEnd?: () => void;
  onPause?: () => void;
  isPaused?: boolean;
  isRecording?: boolean;
  isIdle?: boolean;
  onStartRecording?: () => void;
  onSampleToggle?: () => void;
  samplePlaying?: boolean;
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
  isIdle = false,
  onStartRecording,
  onSampleToggle,
  samplePlaying = false,
}: HeaderProps) {
  const { theme, toggle: toggleTheme } = useTheme();
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!sessionStart || isPaused) return;
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - sessionStart.getTime()) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [sessionStart, isPaused]);

  return (
    <header className="flex h-14 items-center justify-between border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-6 shadow-sm">
      {/* Left: Logo */}
      <div className="flex items-center gap-3">
        <Link to="/dashboard" className="flex items-center gap-2">
          <img src="/icon.png" alt="Open Attend" className="h-8 w-8 rounded-lg" />
          <span className="text-lg font-bold text-slate-900 dark:text-slate-100">Open Attend</span>
        </Link>

        {mode && (
          <span className="rounded-full bg-clinical-100 dark:bg-clinical-900/40 px-3 py-0.5 text-xs font-medium text-clinical-700 dark:bg-clinical-900 dark:text-clinical-300">
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
          <span className="font-mono text-sm text-slate-500 dark:text-slate-400">
            {formatElapsed(elapsed)}
          </span>
        </div>
      )}

      {/* Right: Controls */}
      <div className="flex items-center gap-2">
        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 dark:text-slate-400 transition-colors hover:bg-slate-200 dark:hover:bg-slate-700"
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" />
            </svg>
          ) : (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z" />
            </svg>
          )}
        </button>

        {mode === "active_visit" && (
          <>
            {/* Sample button */}
            <button
              onClick={onSampleToggle}
              disabled={isRecording || isPaused}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                samplePlaying
                  ? "bg-alert-100 text-alert-700 hover:bg-alert-200"
                  : "bg-clinical-100 dark:bg-clinical-900/40 text-clinical-700 dark:text-clinical-300 hover:bg-clinical-200"
              } disabled:cursor-not-allowed disabled:opacity-40`}
              title={isRecording ? "Stop mic recording first" : samplePlaying ? "Stop sample" : "Play sample audio"}
            >
              {samplePlaying ? (
                <>
                  <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 24 24">
                    <rect x="6" y="5" width="4" height="14" rx="1" />
                    <rect x="14" y="5" width="4" height="14" rx="1" />
                  </svg>
                  Stop
                </>
              ) : (
                <>
                  <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                  Sample
                </>
              )}
            </button>

            {/* Start Recording button (only when idle) */}
            {isIdle && !samplePlaying && (
              <button
                onClick={onStartRecording}
                className="flex items-center gap-1.5 rounded-lg bg-clinical-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-clinical-700"
              >
                <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 14a3 3 0 003-3V5a3 3 0 10-6 0v6a3 3 0 003 3z" />
                  <path d="M17 11a1 1 0 10-2 0 3 3 0 11-6 0 1 1 0 10-2 0 5 5 0 005 5v2H9a1 1 0 100 2h6a1 1 0 100-2h-3v-2a5 5 0 005-5z" />
                </svg>
                Record
              </button>
            )}

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
