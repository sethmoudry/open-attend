import React, { useCallback, useEffect, useRef, useState } from 'react';
import type { Speaker, SpeakerProfile, TranscriptChunk } from '../types';
import SpeakerRoleSelector from './SpeakerRoleSelector';
import SpeakerLegend, { getSpeakerColor, resolveRole } from './SpeakerLegend';

interface TranscriptPanelProps {
  chunks: TranscriptChunk[];
  speakerProfiles: SpeakerProfile[];
  onRoleChange: (speakerId: string, role: Speaker) => void;
  /** Additional CSS classes for the outer container */
  className?: string;
}

const ROLE_LABELS: Record<Speaker, string> = {
  doctor: 'DR',
  patient: 'PT',
  parent: 'PA',
  nurse: 'RN',
  interpreter: 'INT',
  other: 'OTH',
  unknown: '??',
};

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export const TranscriptPanel: React.FC<TranscriptPanelProps> = ({
  chunks,
  speakerProfiles,
  onRoleChange,
  className = '',
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [openSelector, setOpenSelector] = useState<string | null>(null);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setAutoScroll(atBottom);
  }, []);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chunks, autoScroll]);

  return (
    <div className={`flex h-full flex-col rounded-2xl bg-gray-900 shadow-lg ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 px-5 py-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
          Live Transcript
        </h2>
        <span className="text-xs text-gray-600">{chunks.length} segments</span>
      </div>

      {/* Speaker Legend */}
      {speakerProfiles.length > 0 && (
        <SpeakerLegend profiles={speakerProfiles} onRoleChange={onRoleChange} />
      )}

      {/* Scrollable transcript body */}
      <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto px-5 py-3">
        {chunks.length === 0 ? (
          <p className="py-12 text-center text-sm text-gray-600">
            Transcript will appear here once recording begins.
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {chunks.map((chunk) => {
              const role = resolveRole(chunk.speaker_id, chunk.speaker, speakerProfiles);
              const badgeColor = getSpeakerColor(chunk.speaker_id, chunk.speaker, speakerProfiles);
              const speakerTag = chunk.speaker_id
                ? `${ROLE_LABELS[role]} (${chunk.speaker_id})`
                : ROLE_LABELS[role];

              return (
                <div key={chunk.id} className="group flex gap-3">
                  {/* Timestamp */}
                  <span className="mt-0.5 shrink-0 font-mono text-xs text-gray-600">
                    [{formatTimestamp(chunk.timestamp_start)}]
                  </span>

                  {/* Speaker badge + text */}
                  <div className="min-w-0">
                    <span className="relative inline-block">
                      <button
                        onClick={() => {
                          if (chunk.speaker_id) {
                            setOpenSelector(
                              openSelector === chunk.id ? null : chunk.id,
                            );
                          }
                        }}
                        className={`mr-1.5 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold uppercase leading-none transition-opacity ${badgeColor} ${
                          chunk.speaker_id ? 'cursor-pointer hover:opacity-80' : 'cursor-default'
                        }`}
                        title={chunk.speaker_id ? 'Click to reassign role' : undefined}
                      >
                        {speakerTag}
                      </button>
                      {openSelector === chunk.id && chunk.speaker_id && (
                        <SpeakerRoleSelector
                          speakerId={chunk.speaker_id}
                          currentRole={role}
                          onSelect={(sid, r) => {
                            onRoleChange(sid, r);
                            setOpenSelector(null);
                          }}
                          onClose={() => setOpenSelector(null)}
                        />
                      )}
                    </span>
                    <span className="text-sm leading-relaxed text-gray-200">{chunk.text}</span>
                  </div>

                  {/* Processing indicator */}
                  {!chunk.processed && (
                    <span
                      className="ml-auto mt-0.5 shrink-0 text-xs text-yellow-600"
                      title="Processing"
                    >
                      ...
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Auto-scroll indicator */}
      {!autoScroll && chunks.length > 0 && (
        <button
          onClick={() => {
            setAutoScroll(true);
            if (scrollRef.current) {
              scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
            }
          }}
          className="mx-auto mb-3 rounded-full bg-gray-800 px-3 py-1 text-xs text-gray-400 transition-colors hover:bg-gray-700 hover:text-gray-200"
        >
          Scroll to latest
        </button>
      )}
    </div>
  );
};

export default TranscriptPanel;
