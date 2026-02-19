import React from "react";
import type { DiagnosisCode } from "../../types";

interface CodeCardProps {
  code: DiagnosisCode;
  onToggleConfirm: (code: string) => void;
}

function confidenceColor(confidence: number): string {
  if (confidence >= 0.85) return "bg-emerald-500";
  if (confidence >= 0.7) return "bg-yellow-500";
  return "bg-orange-500";
}

const CodeCard: React.FC<CodeCardProps> = ({ code, onToggleConfirm }) => {
  const borderClass = code.confirmed
    ? "border-emerald-600 bg-slate-50 dark:bg-slate-900/80"
    : "border-dashed border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-900/40";

  return (
    <div
      className={`flex items-start gap-3 rounded-lg border p-3 transition-colors ${borderClass}`}
    >
      {/* Checkbox */}
      <input
        type="checkbox"
        checked={code.confirmed}
        onChange={() => onToggleConfirm(code.code)}
        className="mt-1 h-4 w-4 shrink-0 cursor-pointer rounded border-slate-300 dark:border-slate-500 bg-slate-100 dark:bg-slate-800 text-emerald-500 focus:ring-emerald-500 focus:ring-offset-0"
      />

      {/* Code details */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-bold text-slate-900 dark:text-white">
            {code.code}
          </span>
          <span className="rounded bg-slate-200 dark:bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {code.source_section}
          </span>
        </div>
        <p className="mt-0.5 text-sm leading-snug text-slate-600 dark:text-slate-300">
          {code.description}
        </p>

        {/* Confidence bar */}
        <div className="mt-2 flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
            <div
              className={`h-full rounded-full transition-all ${confidenceColor(code.confidence)}`}
              style={{ width: `${Math.round(code.confidence * 100)}%` }}
            />
          </div>
          <span className="shrink-0 text-xs tabular-nums text-slate-400 dark:text-slate-500">
            {Math.round(code.confidence * 100)}%
          </span>
        </div>
      </div>
    </div>
  );
};

export default CodeCard;
