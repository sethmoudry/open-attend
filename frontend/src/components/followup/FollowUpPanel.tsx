import React, { useState } from "react";
import type { FollowUpItem, FollowUpType } from "../../types";
import { extractFollowUps, updateFollowUps } from "../../api";
import { FollowUpCard } from "./FollowUpCard";

interface FollowUpPanelProps {
  sessionId: string;
  followUps: FollowUpItem[];
  onSessionUpdate: (updatedFollowUps: FollowUpItem[]) => void;
}

const emptyItem = (): FollowUpItem => ({
  action: "",
  type: "other" as FollowUpType,
  timeframe: "",
  details: "",
});

export const FollowUpPanel: React.FC<FollowUpPanelProps> = ({
  sessionId,
  followUps,
  onSessionUpdate,
}) => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newItem, setNewItem] = useState<FollowUpItem>(emptyItem());

  const handleExtract = async () => {
    setLoading(true);
    try {
      const session = await extractFollowUps(sessionId);
      onSessionUpdate(session.follow_ups);
    } catch (err) {
      console.error("Failed to extract follow-ups:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (index: number, updated: FollowUpItem) => {
    const next = [...followUps];
    next[index] = updated;
    setSaving(true);
    try {
      const session = await updateFollowUps(sessionId, next);
      onSessionUpdate(session.follow_ups);
    } catch (err) {
      console.error("Failed to update follow-ups:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (index: number) => {
    const next = followUps.filter((_, i) => i !== index);
    setSaving(true);
    try {
      const session = await updateFollowUps(sessionId, next);
      onSessionUpdate(session.follow_ups);
    } catch (err) {
      console.error("Failed to remove follow-up:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleAddNew = async () => {
    if (!newItem.action.trim()) return;
    const next = [...followUps, newItem];
    setSaving(true);
    try {
      const session = await updateFollowUps(sessionId, next);
      onSessionUpdate(session.follow_ups);
      setNewItem(emptyItem());
      setAdding(false);
    } catch (err) {
      console.error("Failed to add follow-up:", err);
    } finally {
      setSaving(false);
    }
  };

  const TYPE_OPTIONS: FollowUpType[] = [
    "lab", "imaging", "referral", "medication", "appointment", "other",
  ];
  const typeLabels: Record<FollowUpType, string> = {
    lab: "Lab", imaging: "Imaging", referral: "Referral",
    medication: "Medication", appointment: "Appointment", other: "Other",
  };

  return (
    <div className="card">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          <svg className="h-4 w-4 text-teal-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25ZM6.75 12h.008v.008H6.75V12Zm0 3h.008v.008H6.75V15Zm0 3h.008v.008H6.75V18Z" />
          </svg>
          Follow-ups
          {followUps.length > 0 && (
            <span className="ml-1 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-teal-100 px-1.5 text-[10px] font-bold text-teal-700">
              {followUps.length}
            </span>
          )}
        </h3>
        <button
          onClick={handleExtract}
          disabled={loading}
          className="rounded-md bg-teal-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? (
            <span className="flex items-center gap-1.5">
              <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Extracting...
            </span>
          ) : (
            "Extract Follow-ups"
          )}
        </button>
      </div>

      {/* Saving indicator */}
      {saving && (
        <div className="mt-2 text-[11px] text-slate-400 flex items-center gap-1">
          <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Saving...
        </div>
      )}

      {/* Items list */}
      <div className="mt-3 space-y-2">
        {followUps.length === 0 && !loading ? (
          <p className="text-xs text-slate-400">
            Click "Extract Follow-ups" to pull action items from the visit plan.
          </p>
        ) : (
          followUps.map((item, idx) => (
            <FollowUpCard
              key={`${item.action}-${idx}`}
              item={item}
              index={idx}
              onUpdate={handleUpdate}
              onRemove={handleRemove}
            />
          ))
        )}
      </div>

      {/* Add new item */}
      {adding ? (
        <div className="mt-3 rounded-lg border border-dashed border-teal-300 bg-teal-50/30 p-3 space-y-2">
          <div>
            <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-0.5">
              Action
            </label>
            <input
              type="text"
              value={newItem.action}
              onChange={(e) => setNewItem({ ...newItem, action: e.target.value })}
              placeholder="What needs to happen?"
              className="w-full rounded border border-slate-300 px-2 py-1 text-sm focus:border-teal-400 focus:outline-none focus:ring-1 focus:ring-teal-400"
              autoFocus
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-0.5">
                Type
              </label>
              <select
                value={newItem.type}
                onChange={(e) =>
                  setNewItem({ ...newItem, type: e.target.value as FollowUpType })
                }
                className="w-full rounded border border-slate-300 px-2 py-1 text-sm focus:border-teal-400 focus:outline-none focus:ring-1 focus:ring-teal-400"
              >
                {TYPE_OPTIONS.map((t) => (
                  <option key={t} value={t}>{typeLabels[t]}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-0.5">
                Timeframe
              </label>
              <input
                type="text"
                value={newItem.timeframe}
                onChange={(e) => setNewItem({ ...newItem, timeframe: e.target.value })}
                placeholder="e.g. 2 weeks"
                className="w-full rounded border border-slate-300 px-2 py-1 text-sm focus:border-teal-400 focus:outline-none focus:ring-1 focus:ring-teal-400"
              />
            </div>
          </div>
          <div>
            <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-0.5">
              Details
            </label>
            <input
              type="text"
              value={newItem.details}
              onChange={(e) => setNewItem({ ...newItem, details: e.target.value })}
              placeholder="Additional instructions (optional)"
              className="w-full rounded border border-slate-300 px-2 py-1 text-sm focus:border-teal-400 focus:outline-none focus:ring-1 focus:ring-teal-400"
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button
              onClick={() => { setAdding(false); setNewItem(emptyItem()); }}
              className="rounded px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
            >
              Cancel
            </button>
            <button
              onClick={handleAddNew}
              disabled={!newItem.action.trim()}
              className="rounded bg-teal-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-teal-700 disabled:opacity-50"
            >
              Add
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setAdding(true)}
          className="mt-3 flex w-full items-center justify-center gap-1 rounded-lg border border-dashed border-slate-300 py-2 text-xs text-slate-400 transition-colors hover:border-teal-400 hover:text-teal-600"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          Add follow-up item
        </button>
      )}
    </div>
  );
};

export default FollowUpPanel;
