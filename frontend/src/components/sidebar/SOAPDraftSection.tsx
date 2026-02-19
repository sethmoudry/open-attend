import React, { useState } from "react";
import type { SOAPNote } from "../../types";

interface SOAPDraftSectionProps {
  soapNote: SOAPNote;
  collapsed?: boolean;
  onToggle?: () => void;
}

type SOAPKey = "subjective" | "objective" | "assessment" | "plan";

const soapSections: { key: SOAPKey; label: string; letter: string }[] = [
  { key: "subjective", label: "Subjective", letter: "S" },
  { key: "objective", label: "Objective", letter: "O" },
  { key: "assessment", label: "Assessment", letter: "A" },
  { key: "plan", label: "Plan", letter: "P" },
];

export const SOAPDraftSection: React.FC<SOAPDraftSectionProps> = ({
  soapNote,
  collapsed = false,
  onToggle,
}) => {
  const [expandedSections, setExpandedSections] = useState<Set<SOAPKey>>(
    new Set(["subjective", "objective", "assessment", "plan"]),
  );

  const toggleSubsection = (key: SOAPKey) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const isDrafting = soapNote.status === "draft" || soapNote.status === "in_progress";
  const hasContent = soapSections.some((s) => soapNote[s.key]?.trim());

  return (
    <div className="card">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between text-left"
      >
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          <svg className="h-4 w-4 text-clinical-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
          </svg>
          Draft SOAP Note
          {isDrafting && (
            <span className="ml-1 inline-flex items-center gap-1 rounded-full bg-clinical-100 px-2 py-0.5 text-[10px] font-medium text-clinical-600">
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-clinical-500" />
              Drafting...
            </span>
          )}
        </h3>
        <svg
          className={`h-4 w-4 text-slate-400 transition-transform ${collapsed ? "" : "rotate-180"}`}
          fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {!collapsed && (
        <div className="mt-3 space-y-1">
          {soapSections.map(({ key, label, letter }) => {
            const content = soapNote[key]?.trim();
            const isExpanded = expandedSections.has(key);

            return (
              <div key={key} className="rounded-md border border-slate-100">
                <button
                  onClick={() => toggleSubsection(key)}
                  className="flex w-full items-center gap-2 px-2.5 py-2 text-left text-xs hover:bg-slate-50"
                >
                  <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded bg-clinical-600 text-[10px] font-bold text-white">
                    {letter}
                  </span>
                  <span className="font-semibold text-slate-700">{label}</span>
                  <svg
                    className={`ml-auto h-3 w-3 text-slate-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                    fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                  </svg>
                </button>

                {isExpanded && (
                  <div className="border-t border-slate-100 px-2.5 py-2">
                    {content ? (
                      <p className="whitespace-pre-wrap text-xs leading-relaxed text-slate-600">
                        {content}
                      </p>
                    ) : (
                      <p className="text-xs italic text-slate-400">
                        {isDrafting ? "Drafting..." : "Awaiting data..."}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {hasContent && soapNote.last_updated && (
            <p className="pt-1 text-right text-[10px] text-slate-400">
              Updated{" "}
              {new Date(soapNote.last_updated).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default SOAPDraftSection;
