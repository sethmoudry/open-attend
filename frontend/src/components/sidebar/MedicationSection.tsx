import React from "react";
import type { Medication, InteractionFlag } from "../../types";

interface MedicationSectionProps {
  medications: Medication[];
  interactionFlags: InteractionFlag[];
  collapsed?: boolean;
  onToggle?: () => void;
}

function getInteractionForMed(
  medName: string,
  flags: InteractionFlag[],
): InteractionFlag | null {
  const lower = medName.toLowerCase();
  return (
    flags.find(
      (f) =>
        f.drug_a.toLowerCase() === lower || f.drug_b.toLowerCase() === lower,
    ) ?? null
  );
}

const severityBadge: Record<string, string> = {
  high: "bg-alert-100 text-alert-700",
  moderate: "bg-warning-100 text-warning-600",
  low: "bg-slate-100 dark:bg-slate-900 text-slate-600 dark:text-slate-300",
  none: "bg-success-100 text-success-700",
};

export const MedicationSection: React.FC<MedicationSectionProps> = ({
  medications,
  interactionFlags,
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
            <path strokeLinecap="round" strokeLinejoin="round" d="m20.893 13.393-1.135-1.135a2.252 2.252 0 0 1-.421-.585l-1.08-2.16a.414.414 0 0 0-.663-.107.827.827 0 0 1-.812.21l-1.273-.363a.89.89 0 0 0-.738 1.595l.587.39c.59.395.674 1.23.172 1.732l-.2.2c-.212.212-.33.498-.33.796v.41c0 .409-.11.809-.32 1.158l-1.315 2.191a2.11 2.11 0 0 1-1.81 1.025 1.055 1.055 0 0 1-1.055-1.055v-1.172c0-.92-.56-1.747-1.414-2.089l-.655-.261a2.25 2.25 0 0 1-1.383-2.46l.007-.042a2.25 2.25 0 0 1 .29-.787l.09-.15a2.25 2.25 0 0 1 2.37-1.048l1.178.236a1.125 1.125 0 0 0 1.302-.795l.208-.73a1.125 1.125 0 0 0-.578-1.315l-.665-.332-.091.091a2.25 2.25 0 0 1-1.591.659h-.18a.94.94 0 0 0-.662.274.931.931 0 0 1-1.458-1.137l1.411-2.353a2.25 2.25 0 0 0 .286-.76m11.928 9.869A9 9 0 0 0 8.965 3.525m11.928 9.868A9 9 0 1 1 8.965 3.525" />
          </svg>
          Medications
          {medications.length > 0 && (
            <span className="ml-1 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-clinical-100 dark:bg-clinical-900/40 px-1.5 text-[10px] font-bold text-clinical-700 dark:text-clinical-300">
              {medications.length}
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
        <div className="mt-3 space-y-2">
          {medications.length === 0 ? (
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Medications will be extracted as they are mentioned.
            </p>
          ) : (
            medications.map((med, idx) => {
              const interaction = getInteractionForMed(
                med.name,
                interactionFlags,
              );
              const hasWarning =
                interaction &&
                interaction.severity !== "none" &&
                interaction.severity !== "low";

              return (
                <div
                  key={`${med.name}-${med.chunk_id}-${idx}`}
                  className={`rounded-lg border p-2.5 text-xs ${hasWarning ? "border-warning-500 bg-warning-50" : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800"}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {/* Interaction status icon */}
                      {interaction ? (
                        interaction.severity === "none" ||
                        interaction.severity === "low" ? (
                          <svg className="h-4 w-4 text-success-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                          </svg>
                        ) : (
                          <svg className="h-4 w-4 text-warning-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                          </svg>
                        )
                      ) : (
                        <svg className="h-4 w-4 text-success-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                        </svg>
                      )}
                      <span className="font-semibold text-slate-900 dark:text-slate-100">
                        {med.name}
                      </span>
                    </div>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${med.source === "prescribed" ? "bg-clinical-100 dark:bg-clinical-900/40 text-clinical-700 dark:text-clinical-300" : "bg-slate-100 dark:bg-slate-900 text-slate-600 dark:text-slate-300"}`}
                    >
                      {med.source === "prescribed" ? "Prescribed" : "Reported"}
                    </span>
                  </div>

                  {(med.dose || med.frequency) && (
                    <p className="mt-1 text-slate-500 dark:text-slate-400">
                      {[med.dose, med.frequency].filter(Boolean).join(" - ")}
                    </p>
                  )}

                  {interaction &&
                    interaction.severity !== "none" &&
                    interaction.severity !== "low" && (
                      <div className="mt-1.5 flex items-start gap-1.5">
                        <span
                          className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${severityBadge[interaction.severity]}`}
                        >
                          {interaction.severity}
                        </span>
                        <span className="text-slate-600 dark:text-slate-300">
                          Interaction with {interaction.drug_a.toLowerCase() === med.name.toLowerCase() ? interaction.drug_b : interaction.drug_a}
                          {interaction.mechanism && ` - ${interaction.mechanism}`}
                        </span>
                      </div>
                    )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};

export default MedicationSection;
