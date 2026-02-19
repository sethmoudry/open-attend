import React, { useEffect, useRef, useState } from "react";
import type { ClinicalAlert, AlertType, AlertPriority } from "../../types";

interface AlertsSectionProps {
  alerts: ClinicalAlert[];
  collapsed?: boolean;
  onToggle?: () => void;
}

const priorityStyles: Record<AlertPriority, string> = {
  urgent: "border-alert-500 bg-alert-50 text-alert-700",
  info: "border-slate-300 bg-slate-50 text-slate-700",
};

const priorityDot: Record<AlertPriority, string> = {
  urgent: "bg-alert-500",
  info: "bg-slate-400",
};

function AlertIcon({ type }: { type: AlertType }) {
  switch (type) {
    case "allergy":
      return (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
        </svg>
      );
    case "red_flag":
      return (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v1.5M3 21v-6m0 0 2.77-.693a9 9 0 0 1 6.208.682l.108.054a9 9 0 0 0 6.086.71l3.114-.732a48.524 48.524 0 0 1-.005-10.499l-3.11.732a9 9 0 0 1-6.085-.711l-.108-.054a9 9 0 0 0-6.208-.682L3 4.5M3 15V4.5" />
        </svg>
      );
    case "screening_prompt":
      return (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 5.25h.008v.008H12v-.008Z" />
        </svg>
      );
    case "guideline":
      return (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
        </svg>
      );
  }
}

export const AlertsSection: React.FC<AlertsSectionProps> = ({
  alerts,
  collapsed = false,
  onToggle,
}) => {
  const [prevCount, setPrevCount] = useState(alerts.length);
  const [animateIds, setAnimateIds] = useState<Set<string>>(new Set());
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Track new alerts for entrance animation
  useEffect(() => {
    if (alerts.length > prevCount) {
      const newIds = new Set(
        alerts.slice(prevCount).map((a) => a.source_chunk_id + a.timestamp),
      );
      setAnimateIds(newIds);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setAnimateIds(new Set()), 600);
    }
    setPrevCount(alerts.length);
  }, [alerts, prevCount]);

  const urgentCount = alerts.filter((a) => a.priority === "urgent").length;

  return (
    <div className="card">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between text-left"
      >
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          <svg className="h-4 w-4 text-alert-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
          </svg>
          Alerts
          {alerts.length > 0 && (
            <span className={`ml-1 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full px-1.5 text-[10px] font-bold ${urgentCount > 0 ? "bg-alert-500 text-white" : "bg-slate-200 text-slate-600"}`}>
              {alerts.length}
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
        <div className="mt-3 space-y-2">
          {alerts.length === 0 ? (
            <p className="text-xs text-slate-400">
              Clinical alerts will appear here as they are detected.
            </p>
          ) : (
            alerts.map((alert, idx) => {
              const key = alert.source_chunk_id + alert.timestamp + idx;
              const isNew = animateIds.has(alert.source_chunk_id + alert.timestamp);
              return (
                <div
                  key={key}
                  className={`flex items-start gap-2 rounded-lg border p-2.5 text-xs transition-all ${priorityStyles[alert.priority]} ${isNew ? "animate-pulse" : ""}`}
                >
                  <span className={`mt-0.5 inline-block h-2 w-2 flex-shrink-0 rounded-full ${priorityDot[alert.priority]}`} />
                  <div className="flex-1">
                    <div className="flex items-center gap-1.5">
                      <AlertIcon type={alert.type} />
                      <span className="font-semibold capitalize">
                        {alert.type.replace("_", " ")}
                      </span>
                    </div>
                    <p className="mt-0.5 leading-relaxed">{alert.message}</p>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};

export default AlertsSection;
