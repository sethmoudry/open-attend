import React, { useCallback, useMemo, useState } from "react";
import type { DiagnosisCode, Session } from "../../types";
import { extractCodes, updateCodes } from "../../api";
import CodeCard from "./CodeCard";

interface CodePanelProps {
  session: Session;
  onSessionUpdate: (session: Session) => void;
  className?: string;
}

const CodePanel: React.FC<CodePanelProps> = ({
  session,
  onSessionUpdate,
  className = "",
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const icd10Codes = useMemo(
    () => session.diagnosis_codes.filter((c) => c.source_section === "assessment"),
    [session.diagnosis_codes],
  );

  const cptCodes = useMemo(
    () => session.diagnosis_codes.filter((c) => c.source_section === "plan"),
    [session.diagnosis_codes],
  );

  const handleExtract = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const updated = await extractCodes(session.id);
      onSessionUpdate(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Extraction failed");
    } finally {
      setLoading(false);
    }
  }, [session.id, onSessionUpdate]);

  const toggleConfirm = useCallback(
    async (codeValue: string) => {
      const updated = session.diagnosis_codes.map((c) =>
        c.code === codeValue ? { ...c, confirmed: !c.confirmed } : c,
      );
      try {
        const result = await updateCodes(session.id, updated);
        onSessionUpdate(result);
      } catch {
        // Optimistic rollback not needed since we wait for response
      }
    },
    [session.id, session.diagnosis_codes, onSessionUpdate],
  );

  const confirmAll = useCallback(async () => {
    const updated = session.diagnosis_codes.map((c) => ({
      ...c,
      confirmed: true,
    }));
    try {
      const result = await updateCodes(session.id, updated);
      onSessionUpdate(result);
    } catch {
      // silent
    }
  }, [session.id, session.diagnosis_codes, onSessionUpdate]);

  const removeUnchecked = useCallback(async () => {
    const confirmed = session.diagnosis_codes.filter((c) => c.confirmed);
    try {
      const result = await updateCodes(session.id, confirmed);
      onSessionUpdate(result);
    } catch {
      // silent
    }
  }, [session.id, session.diagnosis_codes, onSessionUpdate]);

  const hasCodes = session.diagnosis_codes.length > 0;
  const hasUnconfirmed = session.diagnosis_codes.some((c) => !c.confirmed);

  const renderSection = (
    title: string,
    codes: DiagnosisCode[],
    badge: string,
  ) => {
    if (codes.length === 0) return null;
    return (
      <div>
        <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {title}
          <span className="rounded-full bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-[10px] text-slate-400 dark:text-slate-500">
            {badge}
          </span>
        </h3>
        <div className="flex flex-col gap-2">
          {codes.map((code) => (
            <CodeCard
              key={code.code}
              code={code}
              onToggleConfirm={toggleConfirm}
            />
          ))}
        </div>
      </div>
    );
  };

  return (
    <div
      className={`flex flex-col rounded-xl bg-white dark:bg-slate-900 shadow-sm ${className}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-700 px-5 py-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Billing Codes
        </h2>
        {hasCodes && (
          <span className="text-xs text-slate-500 dark:text-slate-500">
            {session.diagnosis_codes.filter((c) => c.confirmed).length}/
            {session.diagnosis_codes.length} confirmed
          </span>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {/* Extract button */}
        {!hasCodes && !loading && (
          <div className="flex flex-col items-center gap-3 py-8">
            <p className="text-sm text-slate-400 dark:text-slate-500">
              Extract ICD-10 and CPT codes from the SOAP note.
            </p>
            <button
              onClick={handleExtract}
              className="rounded-lg bg-clinical-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-clinical-500"
            >
              Extract Codes
            </button>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center gap-2 py-12">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
            <span className="text-sm text-slate-500 dark:text-slate-400">
              Extracting codes...
            </span>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-3 rounded-lg bg-red-50 dark:bg-red-900/30 p-3 text-sm text-red-600 dark:text-red-400">
            {error}
          </div>
        )}

        {/* Code sections */}
        {hasCodes && !loading && (
          <div className="flex flex-col gap-5">
            {renderSection(
              "ICD-10 Diagnoses",
              icd10Codes,
              `${icd10Codes.length}`,
            )}
            {renderSection("CPT Procedures", cptCodes, `${cptCodes.length}`)}
          </div>
        )}
      </div>

      {/* Footer actions */}
      {hasCodes && !loading && (
        <div className="flex items-center gap-2 border-t border-slate-200 dark:border-slate-700 px-5 py-3">
          <button
            onClick={handleExtract}
            className="rounded-lg border border-slate-300 dark:border-slate-700 px-3 py-1.5 text-xs text-slate-500 dark:text-slate-400 transition-colors hover:border-slate-400 hover:text-slate-700 dark:hover:border-slate-500 dark:hover:text-slate-200"
          >
            Re-extract
          </button>
          <div className="flex-1" />
          {hasUnconfirmed && (
            <button
              onClick={confirmAll}
              className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-emerald-500"
            >
              Confirm All
            </button>
          )}
          <button
            onClick={removeUnchecked}
            className="rounded-lg border border-red-300 dark:border-red-800 px-3 py-1.5 text-xs text-red-600 dark:text-red-400 transition-colors hover:border-red-600 hover:text-red-300"
          >
            Remove Unchecked
          </button>
        </div>
      )}
    </div>
  );
};

export default CodePanel;
