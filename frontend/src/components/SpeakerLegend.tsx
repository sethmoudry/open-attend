import React, { useState } from 'react';
import type { Speaker, SpeakerProfile } from '../types';
import SpeakerRoleSelector from './SpeakerRoleSelector';

/** Color map for speaker roles -- badge background classes */
export const SPEAKER_BADGE_COLORS: Record<Speaker, string> = {
  doctor: 'bg-blue-600 text-white',
  patient: 'bg-emerald-600 text-white',
  parent: 'bg-purple-600 text-white',
  nurse: 'bg-teal-600 text-white',
  interpreter: 'bg-amber-600 text-white',
  other: 'bg-slate-500 text-white',
  unknown: 'bg-gray-400 text-white',
};

/** Fallback colors for speakers before role assignment, based on speaker index */
const SPEAKER_INDEX_COLORS = [
  'bg-blue-500 text-white',
  'bg-emerald-500 text-white',
  'bg-purple-500 text-white',
  'bg-teal-500 text-white',
  'bg-amber-500 text-white',
  'bg-rose-500 text-white',
  'bg-indigo-500 text-white',
  'bg-cyan-500 text-white',
];

export function getSpeakerColor(
  speakerId: string | undefined,
  role: Speaker,
  profiles: SpeakerProfile[],
): string {
  // If role is known (not unknown), use the role color
  const effectiveRole = resolveRole(speakerId, role, profiles);
  if (effectiveRole && effectiveRole !== 'unknown') {
    return SPEAKER_BADGE_COLORS[effectiveRole];
  }

  // Fall back to index-based color for consistent coloring of unknown speakers
  if (speakerId) {
    const idx = extractSpeakerIndex(speakerId);
    return SPEAKER_INDEX_COLORS[idx % SPEAKER_INDEX_COLORS.length];
  }

  return SPEAKER_BADGE_COLORS.unknown;
}

export function resolveRole(
  speakerId: string | undefined,
  fallbackRole: Speaker,
  profiles: SpeakerProfile[],
): Speaker {
  if (!speakerId) return fallbackRole;
  const profile = profiles.find((p) => p.consistent_id === speakerId);
  if (profile?.role) return profile.role;
  return fallbackRole;
}

function extractSpeakerIndex(speakerId: string): number {
  const match = speakerId.match(/(\d+)$/);
  return match ? parseInt(match[1], 10) : 0;
}

const ROLE_LABELS: Record<Speaker, string> = {
  doctor: 'Doctor',
  patient: 'Patient',
  parent: 'Parent',
  nurse: 'Nurse',
  interpreter: 'Interpreter',
  other: 'Other',
  unknown: 'Unknown',
};

interface SpeakerLegendProps {
  profiles: SpeakerProfile[];
  onRoleChange: (speakerId: string, role: Speaker) => void;
}

const SpeakerLegend: React.FC<SpeakerLegendProps> = ({ profiles, onRoleChange }) => {
  const [openSelector, setOpenSelector] = useState<string | null>(null);

  if (profiles.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-6 py-2">
      <span className="text-[10px] font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">
        Speakers:
      </span>
      {profiles.map((profile) => {
        const role = profile.role ?? 'unknown';
        const colorClass = getSpeakerColor(profile.consistent_id, role, profiles);
        return (
          <div key={profile.consistent_id} className="relative">
            <button
              onClick={() =>
                setOpenSelector(
                  openSelector === profile.consistent_id ? null : profile.consistent_id,
                )
              }
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium transition-opacity hover:opacity-80 ${colorClass}`}
              title={`Click to reassign ${profile.consistent_id}`}
            >
              <span className="opacity-70">{profile.consistent_id}:</span>
              <span>{ROLE_LABELS[role]}</span>
            </button>
            {openSelector === profile.consistent_id && (
              <SpeakerRoleSelector
                speakerId={profile.consistent_id}
                currentRole={profile.role}
                onSelect={onRoleChange}
                onClose={() => setOpenSelector(null)}
              />
            )}
          </div>
        );
      })}
    </div>
  );
};

export default SpeakerLegend;
