import React, { useCallback, useRef, useState } from "react";
import type { ImageAnalysis } from "../../types";
import { uploadImage } from "../../api";
import ImageMatchCard from "./ImageMatchCard";

interface ImageAnalysisPanelProps {
  sessionId: string;
  analyses: ImageAnalysis[];
  onAnalysisAdded: (analysis: ImageAnalysis) => void;
}

const ImageAnalysisPanel: React.FC<ImageAnalysisPanelProps> = ({
  sessionId,
  analyses,
  onAnalysisAdded,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      setUploading(true);
      setError(null);

      try {
        const analysis = await uploadImage(sessionId, file);
        onAnalysisAdded(analysis);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setUploading(false);
        // Reset input so same file can be re-uploaded
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    },
    [sessionId, onAnalysisAdded],
  );

  return (
    <div className="space-y-4">
      {/* Header + upload button */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
          Image Analysis
        </h3>
        <label
          className={`inline-flex cursor-pointer items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
            uploading
              ? "bg-gray-700 text-gray-400 cursor-wait"
              : "bg-indigo-600 text-white hover:bg-indigo-500"
          }`}
        >
          {uploading ? (
            <>
              <svg
                className="h-3.5 w-3.5 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Analyzing...
            </>
          ) : (
            <>
              <svg
                className="h-3.5 w-3.5"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.338-2.32 3 3 0 013.523 3.596A4.5 4.5 0 0118 19.5H6.75z"
                />
              </svg>
              Upload Image
            </>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleUpload}
            disabled={uploading}
          />
        </label>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-md border border-red-800 bg-red-900/30 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {/* Empty state */}
      {analyses.length === 0 && !uploading && (
        <p className="text-center text-sm text-gray-500 py-6">
          No images uploaded yet. Upload a medical image for AI-assisted analysis.
        </p>
      )}

      {/* Analysis cards */}
      {analyses.map((analysis) => (
        <div
          key={analysis.id}
          className="space-y-3 rounded-lg border border-gray-700 bg-gray-800/60 p-4"
        >
          {/* Image preview */}
          <div className="flex gap-3">
            <div className="h-20 w-20 shrink-0 overflow-hidden rounded-md bg-gray-700">
              <img
                src={analysis.image_url}
                alt="Uploaded medical image"
                className="h-full w-full object-cover"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = "none";
                }}
              />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm leading-relaxed text-gray-300">
                {analysis.clinical_description}
              </p>
            </div>
          </div>

          {/* Similar conditions */}
          {analysis.similar_conditions.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Similar Conditions
              </h4>
              <div className="grid gap-2">
                {analysis.similar_conditions.map((cond, idx) => (
                  <ImageMatchCard key={idx} condition={cond} />
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default ImageAnalysisPanel;
