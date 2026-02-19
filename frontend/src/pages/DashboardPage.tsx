import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listSessions } from "../api";
import type { SessionSummary } from "../types";

const MODE_BADGE: Record<string, { label: string; color: string }> = {
  active_visit: { label: "In Progress", color: "bg-amber-100 text-amber-700" },
  post_visit: { label: "Completed", color: "bg-success-100 text-success-700" },
};

const VISIT_LABELS: Record<string, string> = {
  urgent: "Urgent Care",
  new_patient: "New Patient",
  follow_up: "Follow-Up",
  in_person: "In-Person",
  telehealth: "Telehealth",
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listSessions()
      .then(setSessions)
      .catch((err) => console.error("Failed to load sessions:", err))
      .finally(() => setLoading(false));
  }, []);

  const activeSessions = sessions.filter((s) => s.mode === "active_visit");
  const completedSessions = sessions.filter((s) => s.mode === "post_visit");

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <nav className="flex items-center justify-between border-b border-slate-200 bg-white px-8 py-4">
        <button onClick={() => navigate("/")} className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-clinical-600">
            <svg
              className="h-5 w-5 text-white"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
              />
            </svg>
          </div>
          <span className="text-xl font-bold text-slate-900">Scribe</span>
        </button>
        <button
          onClick={() => navigate("/setup")}
          className="flex items-center gap-2 rounded-lg bg-clinical-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-clinical-700"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          New Visit
        </button>
      </nav>

      <div className="mx-auto max-w-5xl px-8 py-8">
        <h1 className="text-2xl font-bold text-slate-900">Patient Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          {sessions.length} patient{sessions.length !== 1 ? "s" : ""} today
        </p>

        {loading ? (
          <div className="mt-12 text-center text-sm text-slate-400">Loading sessions...</div>
        ) : sessions.length === 0 ? (
          <div className="mt-12 text-center">
            <p className="text-sm text-slate-500">No sessions yet.</p>
            <button
              onClick={() => navigate("/setup")}
              className="mt-4 rounded-lg bg-clinical-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-clinical-700"
            >
              Start First Visit
            </button>
          </div>
        ) : (
          <>
            {/* Active Sessions */}
            {activeSessions.length > 0 && (
              <section className="mt-6">
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-amber-600">
                  <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-500" />
                  Active Visits ({activeSessions.length})
                </h2>
                <div className="grid gap-3">
                  {activeSessions.map((s) => (
                    <SessionCard key={s.id} session={s} onClick={() => navigate(`/session/${s.id}`)} />
                  ))}
                </div>
              </section>
            )}

            {/* Completed Sessions */}
            {completedSessions.length > 0 && (
              <section className="mt-8">
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
                  Completed ({completedSessions.length})
                </h2>
                <div className="grid gap-3">
                  {completedSessions.map((s) => (
                    <SessionCard key={s.id} session={s} onClick={() => navigate(`/session/${s.id}/review`)} />
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function SessionCard({ session, onClick }: { session: SessionSummary; onClick: () => void }) {
  const badge = MODE_BADGE[session.mode] ?? { label: session.mode, color: "bg-slate-100 text-slate-600" };
  const name = session.patient_context?.name || "Unknown Patient";
  const age = session.patient_context?.age;
  const complaint = session.patient_context?.chief_complaint;
  const visitLabel = VISIT_LABELS[session.visit_type] ?? session.visit_type;

  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-4 rounded-xl border border-slate-200 bg-white px-5 py-4 text-left shadow-sm transition-all hover:border-clinical-300 hover:shadow-md"
    >
      {/* Avatar */}
      <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full bg-clinical-100 text-sm font-bold text-clinical-700">
        {name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate font-semibold text-slate-900">{name}</span>
          {age && <span className="text-xs text-slate-400">{age}y</span>}
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${badge.color}`}>
            {badge.label}
          </span>
        </div>
        {complaint && (
          <p className="mt-0.5 truncate text-sm text-slate-500">{complaint}</p>
        )}
      </div>

      {/* Meta */}
      <div className="flex flex-shrink-0 flex-col items-end gap-1">
        <span className="text-xs text-slate-400">{timeAgo(session.created_at)}</span>
        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
          {visitLabel}
        </span>
        <span className="text-[10px] text-slate-400">
          {session.transcript_chunk_count} chunks
        </span>
      </div>

      {/* Arrow */}
      <svg className="h-4 w-4 flex-shrink-0 text-slate-300" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
      </svg>
    </button>
  );
}
