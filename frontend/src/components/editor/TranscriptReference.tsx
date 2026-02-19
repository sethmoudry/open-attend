import { useCallback, useMemo, useState } from "react";
import type { TranscriptChunk } from "../../types";

type SoapSectionKey = "subjective" | "objective" | "assessment" | "plan";

interface TranscriptReferenceProps {
  chunks: TranscriptChunk[];
  /** Called when user pins selected text to a SOAP section */
  onPinToSection?: (section: SoapSectionKey, text: string) => void;
}

const SECTION_OPTIONS: { key: SoapSectionKey; label: string; abbrev: string }[] = [
  { key: "subjective", label: "Subjective", abbrev: "S" },
  { key: "objective", label: "Objective", abbrev: "O" },
  { key: "assessment", label: "Assessment", abbrev: "A" },
  { key: "plan", label: "Plan", abbrev: "P" },
];

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function TranscriptReference({
  chunks,
  onPinToSection,
}: TranscriptReferenceProps) {
  const [collapsed, setCollapsed] = useState(true);
  const [search, setSearch] = useState("");
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const [selectedText, setSelectedText] = useState("");
  const [showPinMenu, setShowPinMenu] = useState(false);

  const filtered = useMemo(() => {
    if (!search.trim()) return chunks;
    const q = search.toLowerCase();
    return chunks.filter((c) => c.text.toLowerCase().includes(q));
  }, [chunks, search]);

  const handleTextSelect = useCallback(() => {
    const sel = window.getSelection();
    const text = sel?.toString().trim() || "";
    if (text.length > 0) {
      setSelectedText(text);
      setShowPinMenu(true);
    } else {
      setShowPinMenu(false);
    }
  }, []);

  const handlePin = useCallback(
    (section: SoapSectionKey) => {
      if (selectedText && onPinToSection) {
        onPinToSection(section, selectedText);
      }
      setShowPinMenu(false);
      setSelectedText("");
      window.getSelection()?.removeAllRanges();
    },
    [selectedText, onPinToSection],
  );

  const speakerColor: Record<string, string> = {
    doctor: "text-blue-600",
    physician: "text-blue-600",
    patient: "text-emerald-600 dark:text-emerald-400",
    unknown: "text-slate-400 dark:text-slate-500",
    other: "text-slate-400 dark:text-slate-500",
  };

  const speakerBg: Record<string, string> = {
    doctor: "bg-blue-50 dark:bg-blue-900/30",
    physician: "bg-blue-50 dark:bg-blue-900/30",
    patient: "bg-emerald-50 dark:bg-emerald-900/30",
    unknown: "bg-slate-50 dark:bg-slate-900",
    other: "bg-slate-50 dark:bg-slate-900",
  };

  return (
    <div className="border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
      {/* Toggle header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex w-full items-center justify-between px-6 py-3 text-left transition-colors hover:bg-slate-50 dark:bg-slate-900"
      >
        <div className="flex items-center gap-2">
          <svg
            className={`h-4 w-4 text-slate-400 dark:text-slate-500 transition-transform ${collapsed ? "" : "rotate-180"}`}
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="m4.5 15.75 7.5-7.5 7.5 7.5"
            />
          </svg>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Full Transcript
          </h3>
          <span className="rounded-full bg-slate-100 dark:bg-slate-900 px-2 py-0.5 text-xs text-slate-500 dark:text-slate-400">
            {chunks.length} segments
          </span>
        </div>
        <span className="text-xs text-slate-400 dark:text-slate-500">
          {collapsed ? "Click to expand" : "Click to collapse"}
        </span>
      </button>

      {/* Expandable content */}
      {!collapsed && (
        <div className="border-t border-slate-100 dark:border-slate-700">
          {/* Search bar */}
          <div className="px-6 py-3">
            <div className="relative">
              <svg
                className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 dark:text-slate-500"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"
                />
              </svg>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search transcript..."
                className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 py-2 pl-10 pr-4 text-sm text-slate-800 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500 focus:border-clinical-300 focus:outline-none focus:ring-1 focus:ring-clinical-300"
              />
              {search && (
                <button
                  onClick={() => setSearch("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:text-slate-300"
                >
                  <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>
              )}
            </div>
            {search && (
              <p className="mt-1.5 text-xs text-slate-400 dark:text-slate-500">
                {filtered.length} of {chunks.length} segments match
              </p>
            )}
          </div>

          {/* Pin-to-section floating bar */}
          {showPinMenu && selectedText && (
            <div className="mx-6 mb-2 flex items-center gap-2 rounded-lg border border-clinical-200 dark:border-clinical-700 bg-clinical-50 dark:bg-clinical-900/30 px-3 py-2">
              <span className="text-xs font-medium text-clinical-700 dark:text-clinical-300">
                Pin to:
              </span>
              {SECTION_OPTIONS.map((s) => (
                <button
                  key={s.key}
                  onClick={() => handlePin(s.key)}
                  className="rounded bg-white dark:bg-slate-800 px-2 py-1 text-xs font-medium text-slate-700 dark:text-slate-300 shadow-sm transition-colors hover:bg-clinical-100 dark:bg-clinical-900/40 hover:text-clinical-800 dark:text-clinical-200"
                >
                  {s.abbrev} - {s.label}
                </button>
              ))}
              <button
                onClick={() => {
                  setShowPinMenu(false);
                  setSelectedText("");
                  window.getSelection()?.removeAllRanges();
                }}
                className="ml-auto text-xs text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:text-slate-300"
              >
                Cancel
              </button>
            </div>
          )}

          {/* Transcript chunks */}
          <div
            className="max-h-80 space-y-1 overflow-y-auto px-6 pb-4"
            onMouseUp={handleTextSelect}
          >
            {filtered.length === 0 ? (
              <p className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">
                {chunks.length === 0
                  ? "No transcript available"
                  : "No segments match your search"}
              </p>
            ) : (
              filtered.map((chunk) => (
                <div
                  key={chunk.id}
                  onClick={() =>
                    setHighlightedId(
                      highlightedId === chunk.id ? null : chunk.id,
                    )
                  }
                  className={`cursor-pointer rounded-lg px-3 py-2 transition-colors ${
                    highlightedId === chunk.id
                      ? "border border-clinical-300 bg-clinical-50 dark:bg-clinical-900/30"
                      : `${speakerBg[chunk.speaker] || "bg-slate-50 dark:bg-slate-900"} border border-transparent hover:border-slate-200 dark:border-slate-700`
                  }`}
                >
                  <div className="mb-1 flex items-center gap-2">
                    <span
                      className={`text-xs font-semibold capitalize ${speakerColor[chunk.speaker] || "text-slate-400 dark:text-slate-500"}`}
                    >
                      {chunk.speaker}
                    </span>
                    <span className="text-xs text-slate-300">
                      {formatTime(chunk.timestamp_start)} -{" "}
                      {formatTime(chunk.timestamp_end)}
                    </span>
                  </div>
                  <p className="select-text text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                    {search ? (
                      <HighlightedText text={chunk.text} query={search} />
                    ) : (
                      chunk.text
                    )}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/** Highlights search matches in text */
function HighlightedText({ text, query }: { text: string; query: string }) {
  if (!query.trim()) return <>{text}</>;

  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
  const parts = text.split(regex);

  return (
    <>
      {parts.map((part, i) =>
        regex.test(part) ? (
          <mark key={i} className="rounded bg-yellow-200 dark:bg-yellow-700/40 px-0.5">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}
