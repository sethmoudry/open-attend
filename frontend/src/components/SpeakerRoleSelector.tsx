import React, { useEffect, useRef } from 'react';
import type { Speaker } from '../types';

const ROLE_OPTIONS: Array<{ value: Speaker; label: string }> = [
  { value: 'doctor', label: 'Doctor' },
  { value: 'patient', label: 'Patient' },
  { value: 'parent', label: 'Parent' },
  { value: 'nurse', label: 'Nurse' },
  { value: 'interpreter', label: 'Interpreter' },
  { value: 'other', label: 'Other' },
];

interface SpeakerRoleSelectorProps {
  speakerId: string;
  currentRole: Speaker | null;
  onSelect: (speakerId: string, role: Speaker) => void;
  onClose: () => void;
}

const SpeakerRoleSelector: React.FC<SpeakerRoleSelectorProps> = ({
  speakerId,
  currentRole,
  onSelect,
  onClose,
}) => {
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      ref={ref}
      className="absolute left-0 top-full z-50 mt-1 w-36 rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
    >
      <div className="px-2.5 py-1 text-[10px] font-medium uppercase tracking-wide text-slate-400">
        Assign role
      </div>
      {ROLE_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          onClick={() => {
            onSelect(speakerId, opt.value);
            onClose();
          }}
          className={`flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-xs transition-colors hover:bg-slate-100 ${
            currentRole === opt.value
              ? 'bg-slate-50 font-semibold text-clinical-700'
              : 'text-slate-700'
          }`}
        >
          {opt.label}
          {currentRole === opt.value && (
            <svg className="ml-auto h-3 w-3 text-clinical-600" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
          )}
        </button>
      ))}
    </div>
  );
};

export default SpeakerRoleSelector;
