import React from "react";

interface DifferentialSectionProps {
  differential: string[];
  collapsed?: boolean;
  onToggle?: () => void;
}

export const DifferentialSection: React.FC<DifferentialSectionProps> = ({
  differential,
  collapsed = false,
  onToggle,
}) => {
  return (
    <div className="card">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between text-left"
      >
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          <svg className="h-4 w-4 text-clinical-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0ZM3.75 12h.007v.008H3.75V12Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm-.375 5.25h.007v.008H3.75v-.008Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
          </svg>
          Working Differential
          {differential.length > 0 && (
            <span className="ml-1 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-clinical-100 dark:bg-clinical-900/40 px-1.5 text-[10px] font-bold text-clinical-700 dark:text-clinical-300">
              {differential.length}
            </span>
          )}
        </h3>
        <svg
          className={`h-4 w-4 text-slate-400 dark:text-slate-500 transition-transform ${collapsed ? "" : "rotate-180"}`}
          fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {!collapsed && (
        <div className="mt-3">
          {differential.length === 0 ? (
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Differential diagnoses will build as symptoms are discussed.
            </p>
          ) : (
            <ol className="space-y-1.5">
              {differential.map((dx, idx) => (
                <li
                  key={`${dx}-${idx}`}
                  className="flex items-baseline gap-2 rounded-md px-2 py-1.5 text-xs transition-all hover:bg-slate-50 dark:bg-slate-900"
                >
                  <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-clinical-100 dark:bg-clinical-900/40 text-[10px] font-bold text-clinical-700 dark:text-clinical-300">
                    {idx + 1}
                  </span>
                  <span className="text-slate-700 dark:text-slate-300">{dx}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
};

export default DifferentialSection;
