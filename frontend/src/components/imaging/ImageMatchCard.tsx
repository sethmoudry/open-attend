import React from "react";
import type { SimilarCondition } from "../../types";

interface ImageMatchCardProps {
  condition: SimilarCondition;
}

function scoreColor(score: number): string {
  if (score >= 0.85) return "bg-emerald-500";
  if (score >= 0.6) return "bg-yellow-500";
  return "bg-orange-500";
}

const ImageMatchCard: React.FC<ImageMatchCardProps> = ({ condition }) => {
  const pct = Math.round(condition.similarity_score * 100);

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-3">
      <p className="text-sm font-medium text-gray-200">
        {condition.condition_label}
      </p>

      {/* Similarity bar */}
      <div className="mt-2 flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-gray-700">
          <div
            className={`h-full rounded-full transition-all ${scoreColor(condition.similarity_score)}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="shrink-0 text-xs tabular-nums text-gray-400">
          {pct}%
        </span>
      </div>
    </div>
  );
};

export default ImageMatchCard;
