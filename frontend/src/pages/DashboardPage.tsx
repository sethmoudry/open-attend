import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listSessions, deleteSession } from "../api";
import { useTheme } from "../ThemeContext";
import type { SessionSummary } from "../types";

const MODE_BADGE: Record<string, { label: string; color: string }> = {
  active_visit: { label: "In Progress", color: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300" },
  post_visit: { label: "Completed", color: "bg-success-100 text-success-700 dark:bg-green-900 dark:text-green-300" },
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

function toDateStr(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const { theme, toggle: toggleTheme } = useTheme();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [dateFilter, setDateFilter] = useState("");

  useEffect(() => {
    listSessions()
      .then(setSessions)
      .catch((err) => console.error("Failed to load sessions:", err))
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (id: string) => {
    if (!window.confirm("Delete this session? This cannot be undone.")) return;
    try {
      await deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  const filtered = useMemo(() => {
    let result = sessions;

    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter((s) => {
        const name = (s.patient_context?.name || "").toLowerCase();
        const complaint = (s.patient_context?.chief_complaint || "").toLowerCase();
        return name.includes(q) || complaint.includes(q);
      });
    }

    if (dateFilter) {
      result = result.filter((s) => toDateStr(new Date(s.created_at)) === dateFilter);
    }

    return result;
  }, [sessions, search, dateFilter]);

  const activeSessions = filtered.filter((s) => s.mode === "active_visit");
  const completedSessions = filtered.filter((s) => s.mode === "post_visit");

  return (
    <div className="min-h-screen bg-slate-100 dark:bg-slate-950">
      {/* Header */}
      <nav className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-8 py-4 dark:border-slate-700 dark:bg-slate-900">
        <button onClick={() => navigate("/")} className="flex items-center gap-2">
          <img src="/icon.png" alt="Open Attend" className="h-9 w-9 rounded-lg" />
          <span className="text-xl font-bold text-slate-900 dark:text-slate-100">Open Attend</span>
        </button>
        <div className="flex items-center gap-3">
          <button
            onClick={toggleTheme}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-200 dark:text-slate-400 dark:hover:bg-slate-700"
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? (
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" />
              </svg>
            ) : (
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z" />
              </svg>
            )}
          </button>
          <button
            onClick={() => navigate("/settings")}
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 hover:text-slate-600 dark:hover:text-slate-300"
            title="Settings"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
            </svg>
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
        </div>
      </nav>

      <div className="mx-auto max-w-5xl px-8 py-8">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Patient Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {sessions.length} patient{sessions.length !== 1 ? "s" : ""} today
        </p>

        {/* Search + Date filter */}
        <div className="mt-4 flex items-center gap-3">
          <div className="relative flex-1">
            <svg
              className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
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
              placeholder="Search by patient name or complaint..."
              className="input-field !pl-10"
            />
          </div>
          <input
            type="date"
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
            className="input-field !w-auto"
          />
          {(search || dateFilter) && (
            <button
              onClick={() => { setSearch(""); setDateFilter(""); }}
              className="btn-secondary !px-3 !py-2 text-xs"
            >
              Clear
            </button>
          )}
        </div>

        {loading ? (
          <div className="mt-12 text-center text-sm text-slate-400 dark:text-slate-500">Loading sessions...</div>
        ) : sessions.length === 0 ? (
          <div className="mt-12 text-center">
            <p className="text-sm text-slate-500 dark:text-slate-400">No sessions yet.</p>
            <button
              onClick={() => navigate("/setup")}
              className="mt-4 rounded-lg bg-clinical-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-clinical-700"
            >
              Start First Visit
            </button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="mt-12 text-center text-sm text-slate-400 dark:text-slate-500">
            No sessions match your search.
          </div>
        ) : (
          <>
            {/* Active Sessions */}
            {activeSessions.length > 0 && (
              <section className="mt-6">
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
                  <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-500" />
                  Active Visits ({activeSessions.length})
                </h2>
                <div className="grid gap-3">
                  {activeSessions.map((s) => (
                    <SessionCard key={s.id} session={s} onClick={() => navigate(`/session/${s.id}`)} onDelete={() => handleDelete(s.id)} />
                  ))}
                </div>
              </section>
            )}

            {/* Completed Sessions */}
            {completedSessions.length > 0 && (
              <section className="mt-8">
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  Completed ({completedSessions.length})
                </h2>
                <div className="grid gap-3">
                  {completedSessions.map((s) => (
                    <SessionCard key={s.id} session={s} onClick={() => navigate(`/session/${s.id}/review`)} onDelete={() => handleDelete(s.id)} />
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

function SessionCard({ session, onClick, onDelete }: { session: SessionSummary; onClick: () => void; onDelete: () => void }) {
  const badge = MODE_BADGE[session.mode] ?? { label: session.mode, color: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300" };
  const name = session.patient_context?.name || "Unknown Patient";
  const age = session.patient_context?.age;
  const complaint = session.patient_context?.chief_complaint;
  const visitLabel = VISIT_LABELS[session.visit_type] ?? session.visit_type;

  return (
    <div
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onClick(); }}
      className="group flex w-full cursor-pointer items-center gap-4 rounded-xl border border-slate-200 bg-white px-5 py-4 text-left shadow-sm transition-all hover:border-clinical-300 hover:shadow-md dark:border-slate-700 dark:bg-slate-800 dark:hover:border-clinical-600"
    >
      {/* Avatar */}
      <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full bg-clinical-100 text-sm font-bold text-clinical-700 dark:bg-clinical-900 dark:text-clinical-300">
        {name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate font-semibold text-slate-900 dark:text-slate-100">{name}</span>
          {age && <span className="text-xs text-slate-400 dark:text-slate-500">{age}y</span>}
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${badge.color}`}>
            {badge.label}
          </span>
        </div>
        {complaint && (
          <p className="mt-0.5 truncate text-sm text-slate-500 dark:text-slate-400">{complaint}</p>
        )}
      </div>

      {/* Meta */}
      <div className="flex flex-shrink-0 flex-col items-end gap-1">
        <span className="text-xs text-slate-400 dark:text-slate-500">{timeAgo(session.created_at)}</span>
        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-slate-700 dark:text-slate-400">
          {visitLabel}
        </span>
        <span className="text-[10px] text-slate-400 dark:text-slate-500">
          {session.transcript_chunk_count} segments
        </span>
      </div>

      {/* Delete */}
      <button
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        title="Delete session"
        className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg text-slate-300 opacity-0 transition-all hover:bg-red-50 hover:text-red-500 group-hover:opacity-100 dark:text-slate-600 dark:hover:bg-red-900/30 dark:hover:text-red-400"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
        </svg>
      </button>

      {/* Arrow */}
      <svg className="h-4 w-4 flex-shrink-0 text-slate-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
      </svg>
    </div>
  );
}
