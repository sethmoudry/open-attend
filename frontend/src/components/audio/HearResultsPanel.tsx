import type { HearAnalysisResult } from "../../types";

interface HearResultsPanelProps {
  result: HearAnalysisResult;
}

const SOUND_COLORS: Record<string, string> = {
  cough: "bg-amber-500",
  wheeze: "bg-orange-500",
  stridor: "bg-red-500",
  crackle: "bg-rose-500",
  normal_breathing: "bg-emerald-500",
  speech: "bg-blue-500",
  throat_clearing: "bg-yellow-500",
  silence: "bg-slate-300",
  other: "bg-slate-400",
};

export default function HearResultsPanel({ result }: HearResultsPanelProps) {
  return (
    <div className="space-y-3">
      {/* Detected sounds */}
      {result.detected_sounds?.length > 0 ? (
        <div className="space-y-2">
          {result.detected_sounds.map((sound, i) => (
            <div key={i} className="rounded bg-slate-50 dark:bg-slate-900 px-2.5 py-2">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-xs font-semibold capitalize text-slate-700 dark:text-slate-300">
                  {sound.sound.replace(/_/g, " ")}
                </span>
                <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500">
                  {(sound.confidence * 100).toFixed(0)}%
                </span>
              </div>
              {/* Confidence bar */}
              <div className="mb-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                <div
                  className={`h-full rounded-full transition-all ${SOUND_COLORS[sound.sound] || SOUND_COLORS.other}`}
                  style={{ width: `${Math.max(sound.confidence * 100, 4)}%` }}
                />
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">{sound.description}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs italic text-slate-400 dark:text-slate-500">
          No distinct health sounds detected.
        </p>
      )}

      {/* Clinical relevance */}
      {result.clinical_relevance && (
        <div className="rounded border border-clinical-200 dark:border-clinical-700 bg-clinical-50 dark:bg-clinical-900/30 px-2.5 py-2">
          <h4 className="mb-0.5 text-[10px] font-semibold uppercase text-clinical-600">
            Clinical Relevance
          </h4>
          <p className="text-xs text-clinical-800 dark:text-clinical-200">
            {result.clinical_relevance}
          </p>
        </div>
      )}

      {/* Recommendation */}
      {result.recommendation && (
        <div className="rounded border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/30 px-2.5 py-2">
          <h4 className="mb-0.5 text-[10px] font-semibold uppercase text-amber-600 dark:text-amber-400">
            Recommendation
          </h4>
          <p className="text-xs text-amber-800 dark:text-amber-200">{result.recommendation}</p>
        </div>
      )}

      {/* Meta info */}
      <div className="flex flex-wrap gap-2 text-[10px] text-slate-400 dark:text-slate-500">
        <span>Duration: {result.segment_duration}s</span>
        {result.embedding_windows && (
          <span>HeAR windows: {result.embedding_windows}</span>
        )}
        {result.hear_model_used && (
          <span className="rounded bg-emerald-100 dark:bg-emerald-900/30 px-1.5 py-0.5 text-emerald-600 dark:text-emerald-400">
            HeAR Model
          </span>
        )}
      </div>
    </div>
  );
}
