import { useEffect, useState } from "react";

interface EndVisitModalProps {
  isOpen: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  isLoading: boolean;
  sessionStart: Date;
  chunksProcessed: number;
  medicationsFound: number;
  alertsRaised: number;
}

function formatDuration(start: Date): string {
  const seconds = Math.floor((Date.now() - start.getTime()) / 1000);
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function EndVisitModal({
  isOpen,
  onCancel,
  onConfirm,
  isLoading,
  sessionStart,
  chunksProcessed,
  medicationsFound,
  alertsRaised,
}: EndVisitModalProps) {
  const [duration, setDuration] = useState(() => formatDuration(sessionStart));

  useEffect(() => {
    if (!isOpen) return;
    setDuration(formatDuration(sessionStart));
    const interval = setInterval(() => {
      setDuration(formatDuration(sessionStart));
    }, 1000);
    return () => clearInterval(interval);
  }, [isOpen, sessionStart]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"
        onClick={!isLoading ? onCancel : undefined}
      />

      {/* Modal */}
      <div className="relative z-10 mx-4 w-full max-w-md rounded-2xl bg-white shadow-2xl">
        {/* Header */}
        <div className="border-b border-slate-100 px-6 pt-6 pb-4">
          <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-red-50">
            <svg
              className="h-5 w-5 text-red-500"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M5.25 7.5A2.25 2.25 0 0 1 7.5 5.25h9a2.25 2.25 0 0 1 2.25 2.25v9a2.25 2.25 0 0 1-2.25 2.25h-9a2.25 2.25 0 0 1-2.25-2.25v-9Z"
              />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-slate-900">
            End this visit?
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            This will stop recording and finalize the clinical documentation.
          </p>
        </div>

        {/* Visit Summary */}
        <div className="px-6 py-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Visit Summary
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <SummaryItem label="Duration" value={duration} />
            <SummaryItem label="Chunks Processed" value={String(chunksProcessed)} />
            <SummaryItem label="Medications Found" value={String(medicationsFound)} />
            <SummaryItem label="Alerts Raised" value={String(alertsRaised)} />
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 border-t border-slate-100 px-6 py-4">
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="flex-1 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-50"
          >
            Continue Recording
          </button>
          <button
            onClick={onConfirm}
            disabled={isLoading}
            className="flex-1 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
          >
            {isLoading ? (
              <span className="flex items-center justify-center gap-2">
                <svg
                  className="h-4 w-4 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                Ending...
              </span>
            ) : (
              "End Visit & Review"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="text-sm font-semibold text-slate-700">{value}</p>
    </div>
  );
}
