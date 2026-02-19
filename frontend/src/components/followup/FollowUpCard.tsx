import React, { useState } from "react";
import type { FollowUpItem, FollowUpType } from "../../types";

interface FollowUpCardProps {
  item: FollowUpItem;
  index: number;
  onUpdate: (index: number, updated: FollowUpItem) => void;
  onRemove: (index: number) => void;
}

const TYPE_OPTIONS: FollowUpType[] = [
  "lab",
  "imaging",
  "referral",
  "medication",
  "appointment",
  "other",
];

const typeBadge: Record<FollowUpType, { bg: string; text: string; label: string }> = {
  lab: { bg: "bg-purple-100 dark:bg-purple-900/30", text: "text-purple-700 dark:text-purple-300", label: "Lab" },
  imaging: { bg: "bg-blue-100 dark:bg-blue-900/30", text: "text-blue-700 dark:text-blue-300", label: "Imaging" },
  referral: { bg: "bg-green-100 dark:bg-green-900/30", text: "text-green-700 dark:text-green-300", label: "Referral" },
  medication: { bg: "bg-orange-100 dark:bg-orange-900/30", text: "text-orange-700 dark:text-orange-300", label: "Medication" },
  appointment: { bg: "bg-teal-100 dark:bg-teal-900/30", text: "text-teal-700 dark:text-teal-300", label: "Appointment" },
  other: { bg: "bg-slate-100 dark:bg-slate-900", text: "text-slate-600 dark:text-slate-300", label: "Other" },
};

export const FollowUpCard: React.FC<FollowUpCardProps> = ({
  item,
  index,
  onUpdate,
  onRemove,
}) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<FollowUpItem>({ ...item });

  const badge = typeBadge[item.type] || typeBadge.other;

  const handleSave = () => {
    onUpdate(index, draft);
    setEditing(false);
  };

  const handleCancel = () => {
    setDraft({ ...item });
    setEditing(false);
  };

  if (editing) {
    return (
      <div className="rounded-lg border border-indigo-200 dark:border-indigo-700 bg-indigo-50 dark:bg-indigo-900/30/30 p-3 space-y-2">
        <div>
          <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-0.5">
            Action
          </label>
          <input
            type="text"
            value={draft.action}
            onChange={(e) => setDraft({ ...draft, action: e.target.value })}
            className="w-full rounded border border-slate-300 dark:border-slate-600 px-2 py-1 text-sm focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-0.5">
              Type
            </label>
            <select
              value={draft.type}
              onChange={(e) =>
                setDraft({ ...draft, type: e.target.value as FollowUpType })
              }
              className="w-full rounded border border-slate-300 dark:border-slate-600 px-2 py-1 text-sm focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
            >
              {TYPE_OPTIONS.map((t) => (
                <option key={t} value={t}>
                  {typeBadge[t].label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-0.5">
              Timeframe
            </label>
            <input
              type="text"
              value={draft.timeframe}
              onChange={(e) => setDraft({ ...draft, timeframe: e.target.value })}
              placeholder="e.g. 2 weeks"
              className="w-full rounded border border-slate-300 dark:border-slate-600 px-2 py-1 text-sm focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
            />
          </div>
        </div>

        <div>
          <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-0.5">
            Details
          </label>
          <input
            type="text"
            value={draft.details}
            onChange={(e) => setDraft({ ...draft, details: e.target.value })}
            placeholder="Additional instructions"
            className="w-full rounded border border-slate-300 dark:border-slate-600 px-2 py-1 text-sm focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
          />
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <button
            onClick={handleCancel}
            className="rounded px-2.5 py-1 text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="rounded bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-700"
          >
            Save
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="group flex items-start gap-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-3 transition-colors hover:border-slate-300 dark:border-slate-600">
      {/* Checkbox placeholder */}
      <div className="mt-0.5 h-4 w-4 flex-shrink-0 rounded border-2 border-slate-300 dark:border-slate-600" />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${badge.bg} ${badge.text}`}>
            {badge.label}
          </span>
          {item.timeframe && (
            <span className="text-[11px] text-slate-500 dark:text-slate-400">
              {item.timeframe}
            </span>
          )}
        </div>
        <p className="mt-1 text-sm font-medium text-slate-800 dark:text-slate-200">{item.action}</p>
        {item.details && (
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{item.details}</p>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          onClick={() => setEditing(true)}
          className="rounded p-1 text-slate-400 dark:text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 hover:text-slate-600 dark:text-slate-300"
          title="Edit"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
          </svg>
        </button>
        <button
          onClick={() => onRemove(index)}
          className="rounded p-1 text-slate-400 dark:text-slate-500 hover:bg-red-50 dark:bg-red-900/30 hover:text-red-500"
          title="Remove"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default FollowUpCard;
