import React from "react";
import type { Session } from "../types";

interface NotesPanelProps {
  session: Session | null;
}

const SOAP_LABELS = [
  { key: "subjective", label: "Subjective" },
  { key: "objective", label: "Objective" },
  { key: "assessment", label: "Assessment" },
  { key: "plan", label: "Plan" },
] as const;

export const NotesPanel: React.FC<NotesPanelProps> = ({ session }) => {
  if (!session) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <p className="text-sm text-slate-400">
          Start recording to see clinical notes
        </p>
      </div>
    );
  }

  const chiefComplaint = session.patient_context?.chief_complaint;
  const soap = session.soap_note;
  const medications = session.medications ?? [];
  const alerts = (session.clinical_alerts ?? []).filter(
    (a) => a.priority === "urgent",
  );
  const differential = session.differential ?? [];

  return (
    <div className="space-y-4 px-6 py-4">
      {/* Chief Complaint */}
      <section>
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Chief Complaint
        </h3>
        <p className="text-sm text-slate-700">
          {chiefComplaint || (
            <span className="italic text-slate-400">Awaiting data...</span>
          )}
        </p>
      </section>

      {/* SOAP Draft */}
      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          SOAP Draft
        </h3>
        <div className="space-y-2">
          {SOAP_LABELS.map(({ key, label }) => {
            const value = soap?.[key] ?? "";
            return (
              <div
                key={key}
                className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2"
              >
                <span className="text-[10px] font-bold uppercase tracking-wider text-clinical-600">
                  {label}
                </span>
                <p className="mt-0.5 text-sm text-slate-700">
                  {value.trim() ? (
                    value
                  ) : (
                    <span className="italic text-slate-400">
                      Awaiting data...
                    </span>
                  )}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Medications */}
      <section>
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Medications
        </h3>
        {medications.length === 0 ? (
          <p className="text-sm italic text-slate-400">None yet</p>
        ) : (
          <ul className="space-y-1">
            {medications.map((med, i) => (
              <li key={i} className="flex items-start gap-1.5 text-sm text-slate-700">
                <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-slate-400" />
                <span>
                  <span className="font-medium">{med.name}</span>
                  {med.dose && <span className="text-slate-500"> {med.dose}</span>}
                  {med.frequency && (
                    <span className="text-slate-500"> &middot; {med.frequency}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Clinical Alerts (urgent only) */}
      <section>
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Clinical Alerts
        </h3>
        {alerts.length === 0 ? (
          <p className="text-sm italic text-slate-400">No alerts</p>
        ) : (
          <div className="space-y-1.5">
            {alerts.map((alert, i) => (
              <div
                key={i}
                className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2"
              >
                <span className="mt-0.5 inline-flex items-center rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-bold uppercase leading-none text-white">
                  urgent
                </span>
                <p className="text-sm text-red-800">{alert.message}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Differential */}
      <section>
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Differential
        </h3>
        {differential.length === 0 ? (
          <p className="text-sm italic text-slate-400">Awaiting data...</p>
        ) : (
          <ol className="list-inside list-decimal space-y-0.5 text-sm text-slate-700">
            {differential.map((dx, i) => (
              <li key={i}>{dx}</li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
};

export default NotesPanel;
