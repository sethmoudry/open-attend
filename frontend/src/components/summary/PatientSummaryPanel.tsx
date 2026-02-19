import React, { useState, useRef } from "react";
import type { PatientSummary } from "../../types";
import { generateSummary, updateSummary } from "../../api";

interface PatientSummaryPanelProps {
  sessionId: string;
  summary: PatientSummary | null;
  onSessionUpdate: (updatedSummary: PatientSummary) => void;
}

const READING_LEVEL_LABELS: Record<string, string> = {
  elementary: "Elementary (grades 1-5)",
  middle_school: "Middle school (grades 6-8)",
  high_school: "High school (grades 9-12)",
  college: "College level",
};

export const PatientSummaryPanel: React.FC<PatientSummaryPanelProps> = ({
  sessionId,
  summary,
  onSessionUpdate,
}) => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [previewMode, setPreviewMode] = useState(false);
  const printRef = useRef<HTMLDivElement>(null);

  // Local editing state
  const [editSummary, setEditSummary] = useState(summary?.visit_summary ?? "");
  const [editMeds, setEditMeds] = useState<string[]>(summary?.new_medications ?? []);
  const [editSteps, setEditSteps] = useState<string[]>(summary?.follow_up_steps ?? []);
  const [editSeekCare, setEditSeekCare] = useState(summary?.when_to_seek_care ?? "");

  // Sync local state when summary changes from parent
  React.useEffect(() => {
    setEditSummary(summary?.visit_summary ?? "");
    setEditMeds(summary?.new_medications ?? []);
    setEditSteps(summary?.follow_up_steps ?? []);
    setEditSeekCare(summary?.when_to_seek_care ?? "");
  }, [summary]);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const session = await generateSummary(sessionId);
      if (session.patient_summary) {
        onSessionUpdate(session.patient_summary);
      }
    } catch (err) {
      console.error("Failed to generate summary:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const session = await updateSummary(sessionId, {
        visit_summary: editSummary,
        new_medications: editMeds,
        follow_up_steps: editSteps,
        when_to_seek_care: editSeekCare,
      });
      if (session.patient_summary) {
        onSessionUpdate(session.patient_summary);
      }
    } catch (err) {
      console.error("Failed to save summary:", err);
    } finally {
      setSaving(false);
    }
  };

  const updateListItem = (
    list: string[],
    setter: React.Dispatch<React.SetStateAction<string[]>>,
    index: number,
    value: string,
  ) => {
    const next = [...list];
    next[index] = value;
    setter(next);
  };

  const removeListItem = (
    list: string[],
    setter: React.Dispatch<React.SetStateAction<string[]>>,
    index: number,
  ) => {
    setter(list.filter((_, i) => i !== index));
  };

  const addListItem = (
    setter: React.Dispatch<React.SetStateAction<string[]>>,
  ) => {
    setter((prev) => [...prev, ""]);
  };

  // Preview / PDF-style view
  if (previewMode && summary) {
    return (
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Patient Summary Preview
          </h3>
          <button
            onClick={() => setPreviewMode(false)}
            className="rounded px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-300 border border-slate-300 dark:border-slate-600 hover:bg-slate-50 dark:bg-slate-900"
          >
            Back to Edit
          </button>
        </div>

        <div
          ref={printRef}
          className="mx-auto max-w-lg rounded-xl border-2 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-8 shadow-sm"
        >
          {/* Clinic header */}
          <div className="border-b border-slate-200 dark:border-slate-700 pb-4 mb-6 text-center">
            <h1 className="text-xl font-bold text-slate-800 dark:text-slate-200">Your Visit Summary</h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {new Date().toLocaleDateString("en-US", {
                weekday: "long",
                year: "numeric",
                month: "long",
                day: "numeric",
              })}
            </p>
          </div>

          {/* Visit summary */}
          <div className="mb-6">
            <h2 className="mb-2 text-base font-bold text-slate-700 dark:text-slate-300">
              What happened today
            </h2>
            <p className="text-base leading-relaxed text-slate-600 dark:text-slate-300">
              {editSummary}
            </p>
          </div>

          {/* New medications */}
          {editMeds.length > 0 && (
            <div className="mb-6">
              <h2 className="mb-2 text-base font-bold text-slate-700 dark:text-slate-300">
                Your medications
              </h2>
              <ul className="space-y-2">
                {editMeds.map((med, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 rounded-lg bg-orange-50 dark:bg-orange-900/30 p-3 text-base text-slate-700 dark:text-slate-300"
                  >
                    <svg className="mt-0.5 h-5 w-5 flex-shrink-0 text-orange-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 0-6.23.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0 1 12 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
                    </svg>
                    {med}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Follow-up steps */}
          {editSteps.length > 0 && (
            <div className="mb-6">
              <h2 className="mb-2 text-base font-bold text-slate-700 dark:text-slate-300">
                What to do next
              </h2>
              <ol className="space-y-2">
                {editSteps.map((step, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-3 rounded-lg bg-blue-50 dark:bg-blue-900/30 p-3 text-base text-slate-700 dark:text-slate-300"
                  >
                    <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-blue-200 text-xs font-bold text-blue-700 dark:text-blue-300">
                      {i + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* When to seek care */}
          {editSeekCare && (
            <div className="rounded-lg border-2 border-red-200 dark:border-red-700 bg-red-50 dark:bg-red-900/30 p-4">
              <h2 className="mb-2 flex items-center gap-2 text-base font-bold text-red-700 dark:text-red-300">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                </svg>
                When to call us or go to the ER
              </h2>
              <p className="text-base leading-relaxed text-red-700 dark:text-red-300">
                {editSeekCare}
              </p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          <svg className="h-4 w-4 text-indigo-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
          </svg>
          Patient Summary
          {summary && (
            <span className="ml-1 inline-flex items-center rounded-full bg-green-100 dark:bg-green-900/30 px-1.5 py-0.5 text-[10px] font-medium text-green-700 dark:text-green-300">
              Generated
            </span>
          )}
        </h3>
        <div className="flex gap-2">
          {summary && (
            <button
              onClick={() => setPreviewMode(true)}
              className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-300 transition-colors hover:bg-slate-50 dark:bg-slate-900"
            >
              Preview as PDF
            </button>
          )}
          <button
            onClick={handleGenerate}
            disabled={loading}
            className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? (
              <span className="flex items-center gap-1.5">
                <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Generating...
              </span>
            ) : summary ? (
              "Regenerate"
            ) : (
              "Generate Summary"
            )}
          </button>
        </div>
      </div>

      {/* Reading level indicator */}
      {summary && (
        <div className="mt-2 flex items-center gap-1.5">
          <span className="text-[10px] text-slate-400 dark:text-slate-500">Reading level:</span>
          <span className="inline-flex items-center rounded-full bg-emerald-100 dark:bg-emerald-900/30 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:text-emerald-300">
            {READING_LEVEL_LABELS[summary.reading_level] || summary.reading_level}
          </span>
        </div>
      )}

      {!summary && !loading ? (
        <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
          Generate a plain-language summary to give your patient after the visit.
        </p>
      ) : loading ? (
        <div className="mt-6 flex flex-col items-center justify-center py-8">
          <svg className="h-8 w-8 animate-spin text-indigo-400" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
            Writing your patient's summary in plain language...
          </p>
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          {/* Visit Summary */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
              Visit Summary
            </label>
            <textarea
              value={editSummary}
              onChange={(e) => setEditSummary(e.target.value)}
              rows={4}
              className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm leading-relaxed text-slate-700 dark:text-slate-300 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
            />
          </div>

          {/* New Medications */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
              New Medications
            </label>
            <div className="space-y-1.5">
              {editMeds.map((med, i) => (
                <div key={i} className="flex items-center gap-2">
                  <svg className="h-4 w-4 flex-shrink-0 text-orange-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 0-6.23.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0 1 12 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
                  </svg>
                  <input
                    type="text"
                    value={med}
                    onChange={(e) => updateListItem(editMeds, setEditMeds, i, e.target.value)}
                    className="flex-1 rounded border border-slate-300 dark:border-slate-600 px-2 py-1 text-sm focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  />
                  <button
                    onClick={() => removeListItem(editMeds, setEditMeds, i)}
                    className="rounded p-1 text-slate-400 dark:text-slate-500 hover:bg-red-50 dark:bg-red-900/30 hover:text-red-500"
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))}
              <button
                onClick={() => addListItem(setEditMeds)}
                className="flex items-center gap-1 text-xs text-indigo-500 hover:text-indigo-700"
              >
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                Add medication
              </button>
            </div>
          </div>

          {/* Follow-up Steps */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
              Follow-up Steps
            </label>
            <div className="space-y-1.5">
              {editSteps.map((step, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/30 text-[10px] font-bold text-blue-600">
                    {i + 1}
                  </span>
                  <input
                    type="text"
                    value={step}
                    onChange={(e) => updateListItem(editSteps, setEditSteps, i, e.target.value)}
                    className="flex-1 rounded border border-slate-300 dark:border-slate-600 px-2 py-1 text-sm focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  />
                  <button
                    onClick={() => removeListItem(editSteps, setEditSteps, i)}
                    className="rounded p-1 text-slate-400 dark:text-slate-500 hover:bg-red-50 dark:bg-red-900/30 hover:text-red-500"
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))}
              <button
                onClick={() => addListItem(setEditSteps)}
                className="flex items-center gap-1 text-xs text-indigo-500 hover:text-indigo-700"
              >
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                Add step
              </button>
            </div>
          </div>

          {/* When to Seek Care */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
              When to Seek Care
            </label>
            <textarea
              value={editSeekCare}
              onChange={(e) => setEditSeekCare(e.target.value)}
              rows={3}
              className="w-full rounded-lg border border-red-200 dark:border-red-700 bg-red-50 dark:bg-red-900/30/30 px-3 py-2 text-sm leading-relaxed text-slate-700 dark:text-slate-300 focus:border-red-400 focus:outline-none focus:ring-1 focus:ring-red-400"
              placeholder="Describe warning signs that should prompt the patient to seek care..."
            />
          </div>

          {/* Save button */}
          <div className="flex justify-end">
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-md bg-indigo-600 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default PatientSummaryPanel;
