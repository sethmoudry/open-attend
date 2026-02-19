import React, { useCallback, useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import type { SOAPNote } from "../../types";

interface SOAPDraftSectionProps {
  soapNote: SOAPNote;
  collapsed?: boolean;
  onToggle?: () => void;
  sessionId?: string;
  onSoapUpdated?: (soap: SOAPNote) => void;
}

type SOAPKey = "subjective" | "objective" | "assessment" | "plan";

const soapSections: { key: SOAPKey; label: string; letter: string }[] = [
  { key: "subjective", label: "Subjective", letter: "S" },
  { key: "objective", label: "Objective", letter: "O" },
  { key: "assessment", label: "Assessment", letter: "A" },
  { key: "plan", label: "Plan", letter: "P" },
];

function FormatToolbar({ textareaRef }: { textareaRef: React.RefObject<HTMLTextAreaElement | null> }) {
  const wrapSelection = (before: string, after: string) => {
    const el = textareaRef.current;
    if (!el) return;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const text = el.value;
    const selected = text.slice(start, end);
    const replacement = `${before}${selected}${after}`;
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype, "value"
    )?.set;
    if (nativeInputValueSetter) {
      nativeInputValueSetter.call(el, text.slice(0, start) + replacement + text.slice(end));
      const event = new Event("input", { bubbles: true });
      el.dispatchEvent(event);
    }
    el.focus();
    el.setSelectionRange(start + before.length, start + before.length + selected.length);
  };

  const insertBullet = () => {
    const el = textareaRef.current;
    if (!el) return;
    const start = el.selectionStart;
    const text = el.value;
    const lineStart = text.lastIndexOf("\n", start - 1) + 1;
    const prefix = "- ";
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype, "value"
    )?.set;
    if (nativeInputValueSetter) {
      nativeInputValueSetter.call(el, text.slice(0, lineStart) + prefix + text.slice(lineStart));
      const event = new Event("input", { bubbles: true });
      el.dispatchEvent(event);
    }
    el.focus();
    el.setSelectionRange(start + prefix.length, start + prefix.length);
  };

  return (
    <div className="flex items-center gap-1 border-b border-slate-100 dark:border-slate-700 px-2.5 py-1">
      <button
        type="button"
        onClick={() => wrapSelection("**", "**")}
        className="rounded px-1.5 py-0.5 text-xs font-bold text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
        title="Bold (Ctrl+B)"
      >
        B
      </button>
      <button
        type="button"
        onClick={() => wrapSelection("*", "*")}
        className="rounded px-1.5 py-0.5 text-xs italic text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
        title="Italic (Ctrl+I)"
      >
        I
      </button>
      <button
        type="button"
        onClick={insertBullet}
        className="rounded px-1.5 py-0.5 text-xs text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
        title="Bullet list"
      >
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 6.75h12M8.25 12h12M8.25 17.25h12M3.75 6.75h.007v.008H3.75V6.75Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0ZM3.75 12h.007v.008H3.75V12Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm-.375 5.25h.007v.008H3.75v-.008Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
        </svg>
      </button>
    </div>
  );
}

export const SOAPDraftSection: React.FC<SOAPDraftSectionProps> = ({
  soapNote,
  collapsed = false,
  onToggle,
}) => {
  const [expandedSections, setExpandedSections] = useState<Set<SOAPKey>>(
    new Set(["subjective", "objective", "assessment", "plan"]),
  );
  const [editValues, setEditValues] = useState<Record<SOAPKey, string>>({
    subjective: soapNote.subjective,
    objective: soapNote.objective,
    assessment: soapNote.assessment,
    plan: soapNote.plan,
  });
  const [editingSection, setEditingSection] = useState<SOAPKey | null>(null);
  const textareaRefs = useRef<Record<SOAPKey, HTMLTextAreaElement | null>>({
    subjective: null,
    objective: null,
    assessment: null,
    plan: null,
  });

  // Sync from props when AI updates the note (but not while user is editing that section)
  useEffect(() => {
    setEditValues((prev) => {
      const next = { ...prev };
      for (const key of ["subjective", "objective", "assessment", "plan"] as SOAPKey[]) {
        if (key !== editingSection) {
          next[key] = soapNote[key] || "";
        }
      }
      return next;
    });
  }, [soapNote.subjective, soapNote.objective, soapNote.assessment, soapNote.plan, soapNote.last_updated, editingSection]);

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

  const handleChange = useCallback((key: SOAPKey, value: string) => {
    setEditValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>, key: SOAPKey) => {
    if (e.ctrlKey || e.metaKey) {
      const el = textareaRefs.current[key];
      if (!el) return;
      if (e.key === "b") {
        e.preventDefault();
        const start = el.selectionStart;
        const end = el.selectionEnd;
        const text = el.value;
        const selected = text.slice(start, end);
        const newValue = text.slice(0, start) + `**${selected}**` + text.slice(end);
        handleChange(key, newValue);
      } else if (e.key === "i") {
        e.preventDefault();
        const start = el.selectionStart;
        const end = el.selectionEnd;
        const text = el.value;
        const selected = text.slice(start, end);
        const newValue = text.slice(0, start) + `*${selected}*` + text.slice(end);
        handleChange(key, newValue);
      }
    }
  }, [handleChange]);

  const isDrafting = soapNote.status === "draft" || soapNote.status === "in_progress";
  const hasContent = soapSections.some((s) => editValues[s.key]?.trim());

  return (
    <div className="card">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between text-left"
      >
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          <svg className="h-4 w-4 text-clinical-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
          </svg>
          Draft SOAP Note
          {isDrafting && (
            <span className="ml-1 inline-flex items-center gap-1 rounded-full bg-clinical-100 dark:bg-clinical-900/40 px-2 py-0.5 text-[10px] font-medium text-clinical-600">
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-clinical-500" />
              Drafting...
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
        <div className="mt-3 space-y-1">
          {soapSections.map(({ key, label, letter }) => {
            const isExpanded = expandedSections.has(key);

            return (
              <div key={key} className="rounded-md border border-slate-100 dark:border-slate-700">
                <button
                  onClick={() => toggleSubsection(key)}
                  className="flex w-full items-center gap-2 px-2.5 py-2 text-left text-xs hover:bg-slate-50 dark:bg-slate-900"
                >
                  <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded bg-clinical-600 text-[10px] font-bold text-white">
                    {letter}
                  </span>
                  <span className="font-semibold text-slate-700 dark:text-slate-300">{label}</span>
                  <svg
                    className={`ml-auto h-3 w-3 text-slate-400 dark:text-slate-500 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                    fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                  </svg>
                </button>

                {isExpanded && (
                  <div className="border-t border-slate-100 dark:border-slate-700">
                    {editingSection === key ? (
                      <>
                        <FormatToolbar textareaRef={{ current: textareaRefs.current[key] }} />
                        <textarea
                          ref={(el) => { textareaRefs.current[key] = el; }}
                          value={editValues[key]}
                          onChange={(e) => handleChange(key, e.target.value)}
                          onFocus={() => setEditingSection(key)}
                          onBlur={() => setEditingSection(null)}
                          onKeyDown={(e) => handleKeyDown(e, key)}
                          placeholder={isDrafting ? "AI is drafting..." : "Type here or wait for AI..."}
                          className="w-full resize-y border-0 bg-transparent px-3 py-2.5 text-sm leading-relaxed text-slate-700 dark:text-slate-300 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-0"
                          style={{ minHeight: "120px" }}
                          autoFocus
                        />
                      </>
                    ) : (
                      <div
                        onClick={() => setEditingSection(key)}
                        className="group/edit cursor-text px-3 py-2.5"
                        style={{ minHeight: "120px" }}
                        title="Click to edit"
                      >
                        {editValues[key]?.trim() ? (
                          <div className="soap-markdown prose prose-sm max-w-none text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                            <Markdown>{editValues[key]}</Markdown>
                          </div>
                        ) : (
                          <p className="text-sm italic text-slate-400 dark:text-slate-500">
                            {isDrafting ? "AI is drafting..." : "Click to add content..."}
                          </p>
                        )}
                        <div className="mt-1 flex justify-end opacity-0 transition-opacity group-hover/edit:opacity-100">
                          <span className="rounded bg-slate-100 dark:bg-slate-900 px-1.5 py-0.5 text-[10px] text-slate-400 dark:text-slate-500">
                            Click to edit
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {hasContent && soapNote.last_updated && (
            <p className="pt-1 text-right text-[10px] text-slate-400 dark:text-slate-500">
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
