import React from "react";
import type { LabReport, LabFlag } from "../../types";

interface LabResultsSectionProps {
  labReports: LabReport[];
  collapsed?: boolean;
  onToggle?: () => void;
}

const flagStyles: Record<LabFlag, { text: string; icon: string }> = {
  normal: { text: "text-success-600", icon: "✓" },
  high: { text: "text-alert-600", icon: "↑" },
  low: { text: "text-warning-600", icon: "↓" },
  critical: { text: "font-bold text-alert-700", icon: "⚠" },
};

export const LabResultsSection: React.FC<LabResultsSectionProps> = ({
  labReports,
  collapsed = false,
  onToggle,
}) => {
  const totalResults = labReports.reduce((n, r) => n + r.results.length, 0);

  return (
    <div className="card">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between text-left"
      >
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          <svg
            className="h-4 w-4 text-clinical-500"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714a2.25 2.25 0 0 0 .659 1.591L19 14.5M14.25 3.104c.251.023.501.05.75.082M19 14.5l-1.43 4.294a2.25 2.25 0 0 1-2.134 1.531H8.564a2.25 2.25 0 0 1-2.134-1.531L5 14.5m14 0H5"
            />
          </svg>
          Lab Results
          {labReports.length > 0 && (
            <span className="ml-1 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-clinical-100 px-1.5 text-[10px] font-bold text-clinical-700">
              {totalResults}
            </span>
          )}
        </h3>
        <svg
          className={`h-4 w-4 text-slate-400 transition-transform ${collapsed ? "" : "rotate-180"}`}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="m19.5 8.25-7.5 7.5-7.5-7.5"
          />
        </svg>
      </button>

      {!collapsed && (
        <div className="mt-3 space-y-3">
          {labReports.length === 0 ? (
            <p className="text-xs text-slate-400">No lab reports uploaded</p>
          ) : (
            labReports.map((report) => (
              <div
                key={report.id}
                className="rounded-lg border border-slate-200 bg-white"
              >
                {/* Report header */}
                <div className="border-b border-slate-100 px-2.5 py-2">
                  <p className="text-xs font-semibold text-slate-900">
                    {report.lab_name}
                  </p>
                  <div className="mt-0.5 flex items-center gap-2 text-[10px] text-slate-400">
                    {report.date && <span>{report.date}</span>}
                    {report.date && report.uploaded_at && (
                      <span className="text-slate-300">|</span>
                    )}
                    {report.uploaded_at && (
                      <span>
                        Uploaded{" "}
                        {new Date(report.uploaded_at).toLocaleString([], {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    )}
                  </div>
                </div>

                {/* Results table */}
                {report.results.length > 0 && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-[11px]">
                      <thead>
                        <tr className="border-b border-slate-100 text-left text-[10px] font-medium uppercase tracking-wider text-slate-400">
                          <th className="px-2.5 py-1.5">Test</th>
                          <th className="px-2 py-1.5 text-right">Value</th>
                          <th className="px-2 py-1.5">Unit</th>
                          <th className="px-2 py-1.5">Ref Range</th>
                          <th className="px-2 py-1.5 text-center">Flag</th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.results.map((result, idx) => {
                          const style = flagStyles[result.flag];
                          return (
                            <tr
                              key={`${result.test}-${idx}`}
                              className="border-b border-slate-50 last:border-0"
                            >
                              <td className="px-2.5 py-1.5 font-medium text-slate-700">
                                {result.test}
                              </td>
                              <td
                                className={`px-2 py-1.5 text-right tabular-nums ${style.text}`}
                              >
                                {result.value}
                              </td>
                              <td className="px-2 py-1.5 text-slate-500">
                                {result.unit}
                              </td>
                              <td className="px-2 py-1.5 text-slate-400">
                                {result.reference_range ?? "—"}
                              </td>
                              <td
                                className={`px-2 py-1.5 text-center ${style.text}`}
                              >
                                {style.icon}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default LabResultsSection;
