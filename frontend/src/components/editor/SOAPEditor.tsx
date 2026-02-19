import { useCallback, useEffect, useRef, useState } from "react";
import { updateSOAP } from "../../api";
import type { SOAPNote } from "../../types";

type SectionKey = "subjective" | "objective" | "assessment" | "plan";

interface SOAPSection {
  key: SectionKey;
  label: string;
  abbrev: string;
  color: string;
  bgColor: string;
  placeholder: string;
}

const SECTIONS: SOAPSection[] = [
  {
    key: "subjective",
    label: "Subjective",
    abbrev: "S",
    color: "text-blue-700",
    bgColor: "bg-blue-100",
    placeholder:
      "Patient-reported symptoms, history of present illness, review of systems, medications, allergies, social and family history...",
  },
  {
    key: "objective",
    label: "Objective",
    abbrev: "O",
    color: "text-emerald-700",
    bgColor: "bg-emerald-100",
    placeholder:
      "Vital signs, physical exam findings, lab results, imaging results...",
  },
  {
    key: "assessment",
    label: "Assessment",
    abbrev: "A",
    color: "text-amber-700",
    bgColor: "bg-amber-100",
    placeholder:
      "Working diagnoses, differential diagnoses, clinical reasoning, ICD-10 codes...",
  },
  {
    key: "plan",
    label: "Plan",
    abbrev: "P",
    color: "text-purple-700",
    bgColor: "bg-purple-100",
    placeholder:
      "Treatment orders, prescriptions, referrals, follow-up schedule, patient education...",
  },
];

type SaveStatus = "saved" | "saving" | "unsaved" | "error" | "idle";

interface SOAPEditorProps {
  sessionId: string;
  soapNote: SOAPNote;
  /** Called when SOAP is successfully saved so parent can update its state */
  onSoapUpdated?: (soap: SOAPNote) => void;
}

export default function SOAPEditor({
  sessionId,
  soapNote,
  onSoapUpdated,
}: SOAPEditorProps) {
  // Local editable state per section
  const [values, setValues] = useState<Record<SectionKey, string>>({
    subjective: soapNote.subjective,
    objective: soapNote.objective,
    assessment: soapNote.assessment,
    plan: soapNote.plan,
  });

  // Original AI-generated text for revert
  const [originals, setOriginals] = useState<Record<SectionKey, string>>({
    subjective: soapNote.subjective,
    objective: soapNote.objective,
    assessment: soapNote.assessment,
    plan: soapNote.plan,
  });

  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingRef = useRef<Partial<Record<SectionKey, string>>>({});
  const mountedRef = useRef(true);

  // Sync originals when soapNote prop changes from outside (initial load)
  useEffect(() => {
    setOriginals({
      subjective: soapNote.subjective,
      objective: soapNote.objective,
      assessment: soapNote.assessment,
      plan: soapNote.plan,
    });
    // Only update values if we haven't made local edits (idle/saved state)
    if (saveStatus === "idle" || saveStatus === "saved") {
      setValues({
        subjective: soapNote.subjective,
        objective: soapNote.objective,
        assessment: soapNote.assessment,
        plan: soapNote.plan,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [soapNote.last_updated]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const flush = useCallback(async () => {
    const updates = { ...pendingRef.current };
    pendingRef.current = {};

    if (Object.keys(updates).length === 0) return;

    setSaveStatus("saving");
    try {
      const result = await updateSOAP(sessionId, updates);
      if (!mountedRef.current) return;
      setSaveStatus("saved");
      onSoapUpdated?.(result.soap_note);
    } catch {
      if (!mountedRef.current) return;
      setSaveStatus("error");
    }
  }, [sessionId, onSoapUpdated]);

  const handleChange = useCallback(
    (key: SectionKey, value: string) => {
      setValues((prev) => ({ ...prev, [key]: value }));
      pendingRef.current[key] = value;
      setSaveStatus("unsaved");

      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        flush();
      }, 500);
    },
    [flush],
  );

  const handleRevert = useCallback((key: SectionKey) => {
    setValues((prev) => ({ ...prev, [key]: originals[key] }));
    pendingRef.current[key] = originals[key];
    setSaveStatus("unsaved");

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      flush();
    }, 300);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [originals, flush]);

  // Allow appending text from transcript reference
  const appendToSection = useCallback(
    (key: SectionKey, text: string) => {
      const newValue =
        values[key].length > 0 ? `${values[key]}\n\n${text}` : text;
      handleChange(key, newValue);
    },
    [values, handleChange],
  );

  // Expose appendToSection via a ref-like pattern on the window for cross-component use
  useEffect(() => {
    (window as any).__soapEditorAppend = appendToSection;
    return () => {
      delete (window as any).__soapEditorAppend;
    };
  }, [appendToSection]);

  const statusLabel = {
    idle: "",
    saved: "Saved",
    saving: "Saving...",
    unsaved: "Unsaved changes",
    error: "Save failed",
  };

  const statusColor = {
    idle: "text-slate-400",
    saved: "text-emerald-600",
    saving: "text-amber-500",
    unsaved: "text-amber-500",
    error: "text-red-500",
  };

  return (
    <div className="flex flex-1 flex-col">
      {/* Section header with save status */}
      <div className="flex items-center justify-between border-b border-slate-200 px-6 py-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">SOAP Note</h2>
          <p className="text-xs text-slate-400">
            Review and edit the generated documentation
          </p>
        </div>
        {saveStatus !== "idle" && (
          <div className="flex items-center gap-1.5">
            {saveStatus === "saving" && (
              <svg
                className="h-3 w-3 animate-spin text-amber-500"
                viewBox="0 0 24 24"
                fill="none"
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
            )}
            {saveStatus === "saved" && (
              <svg
                className="h-3 w-3 text-emerald-600"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
            )}
            <span className={`text-xs font-medium ${statusColor[saveStatus]}`}>
              {statusLabel[saveStatus]}
            </span>
          </div>
        )}
      </div>

      {/* SOAP sections */}
      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        {SECTIONS.map((section) => {
          const charCount = values[section.key].length;
          const hasChanged = values[section.key] !== originals[section.key];

          return (
            <div
              key={section.key}
              className="rounded-lg border border-slate-200 bg-white shadow-sm"
            >
              {/* Section header */}
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
                <div className="flex items-center gap-2.5">
                  <span
                    className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${section.bgColor} ${section.color}`}
                  >
                    {section.abbrev}
                  </span>
                  <h3 className="text-sm font-semibold text-slate-900">
                    {section.label}
                  </h3>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs tabular-nums text-slate-400">
                    {charCount.toLocaleString()} chars
                  </span>
                  {hasChanged && (
                    <button
                      onClick={() => handleRevert(section.key)}
                      className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
                      title="Revert to AI draft"
                    >
                      <svg
                        className="h-3 w-3"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={2}
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M9 15 3 9m0 0 6-6M3 9h12a6 6 0 0 1 0 12h-3"
                        />
                      </svg>
                      Revert
                    </button>
                  )}
                </div>
              </div>

              {/* Textarea */}
              <textarea
                value={values[section.key]}
                onChange={(e) => handleChange(section.key, e.target.value)}
                placeholder={section.placeholder}
                rows={6}
                className="w-full resize-y border-0 bg-transparent px-4 py-3 text-sm leading-relaxed text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-0"
                style={{ minHeight: "120px" }}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
