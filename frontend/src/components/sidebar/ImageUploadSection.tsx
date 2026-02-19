import React, { useCallback, useRef, useState } from "react";
import type { ImageAnalysis } from "../../types";
import { uploadImage } from "../../api";

interface ImageUploadSectionProps {
  sessionId: string;
  imageAnalyses: ImageAnalysis[];
  collapsed?: boolean;
  onToggle?: () => void;
}

export const ImageUploadSection: React.FC<ImageUploadSectionProps> = ({
  sessionId,
  imageAnalyses,
  collapsed = false,
  onToggle,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [localAnalyses, setLocalAnalyses] = useState<ImageAnalysis[]>([]);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // Merge server-polled analyses with locally uploaded ones (deduplicated)
  const allAnalyses = [
    ...imageAnalyses,
    ...localAnalyses.filter(
      (la) => !imageAnalyses.some((sa) => sa.id === la.id),
    ),
  ];

  const handleFile = useCallback(
    async (file: File) => {
      if (!file.type.startsWith("image/")) {
        setError("Please select an image file.");
        return;
      }

      setError(null);
      setUploading(true);
      setUploadProgress(10);

      // Show preview
      const objectUrl = URL.createObjectURL(file);
      setPreviewUrl(objectUrl);

      // Simulate progress while waiting for response
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => Math.min(prev + 8, 90));
      }, 400);

      try {
        const result = await uploadImage(sessionId, file);
        setUploadProgress(100);
        setLocalAnalyses((prev) => [...prev, result]);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Upload failed. Try again.",
        );
      } finally {
        clearInterval(progressInterval);
        setTimeout(() => {
          setUploading(false);
          setUploadProgress(0);
          setPreviewUrl(null);
          URL.revokeObjectURL(objectUrl);
        }, 500);
      }
    },
    [sessionId],
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    // Reset so same file can be re-selected
    e.target.value = "";
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <div className="card">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between text-left"
      >
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          <svg
            className="h-4 w-4 text-clinical-500"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0 0 22.5 18.75V5.25A2.25 2.25 0 0 0 20.25 3H3.75A2.25 2.25 0 0 0 1.5 5.25v13.5A2.25 2.25 0 0 0 3.75 21ZM16.5 6.75a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Z"
            />
          </svg>
          Images
          {allAnalyses.length > 0 && (
            <span className="ml-1 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-clinical-100 dark:bg-clinical-900/40 px-1.5 text-[10px] font-bold text-clinical-700 dark:text-clinical-300">
              {allAnalyses.length}
            </span>
          )}
        </h3>
        <svg
          className={`h-4 w-4 text-slate-400 dark:text-slate-500 transition-transform ${collapsed ? "" : "rotate-180"}`}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="m19.5 8.25-7.5 7.5-7.5-7.5"
          />
        </svg>
      </button>

      {!collapsed && (
        <div className="mt-3 space-y-3">
          {/* Drop zone / upload area */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => !uploading && fileInputRef.current?.click()}
            className={`flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border-2 border-dashed p-3 text-center transition-colors ${
              isDragOver
                ? "border-clinical-400 bg-clinical-50 dark:bg-clinical-900/30"
                : "border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-900 hover:border-clinical-300 hover:bg-clinical-50 dark:bg-clinical-900/30/50"
            } ${uploading ? "pointer-events-none opacity-60" : ""}`}
          >
            {uploading && previewUrl ? (
              <>
                <img
                  src={previewUrl}
                  alt="Uploading preview"
                  className="h-12 w-12 rounded object-cover"
                />
                <div className="w-full">
                  <div className="mb-1 text-[10px] font-medium text-clinical-600">
                    Analyzing...
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                    <div
                      className="h-full rounded-full bg-clinical-500 transition-all duration-300"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </div>
              </>
            ) : (
              <>
                <svg
                  className="h-5 w-5 text-slate-400 dark:text-slate-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"
                  />
                </svg>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                  Drop image or{" "}
                  <span className="font-medium text-clinical-600">browse</span>
                </p>
              </>
            )}
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={handleInputChange}
            className="hidden"
          />

          {/* Error message */}
          {error && (
            <div className="flex items-center gap-1.5 rounded-md bg-alert-50 px-2.5 py-1.5 text-xs text-alert-700">
              <svg
                className="h-3.5 w-3.5 flex-shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"
                />
              </svg>
              <span>{error}</span>
              <button
                onClick={() => setError(null)}
                className="ml-auto text-alert-500 hover:text-alert-700"
              >
                <svg
                  className="h-3 w-3"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M6 18 18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
          )}

          {/* Analysis results */}
          {allAnalyses.length === 0 && !uploading ? (
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Upload clinical images for AI analysis during the visit.
            </p>
          ) : (
            allAnalyses.map((analysis) => (
              <div
                key={analysis.id}
                className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-2.5"
              >
                {/* Thumbnail + description */}
                <div className="flex gap-2.5">
                  {analysis.image_url && (
                    <img
                      src={analysis.image_url}
                      alt="Clinical"
                      className="h-14 w-14 flex-shrink-0 rounded object-cover"
                    />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="text-xs leading-relaxed text-slate-700 dark:text-slate-300">
                      {analysis.clinical_description || "No description available."}
                    </p>
                  </div>
                </div>

                {/* Similar conditions */}
                {analysis.similar_conditions.length > 0 && (
                  <div className="mt-2 border-t border-slate-100 dark:border-slate-700 pt-2">
                    <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                      Similar Conditions
                    </p>
                    <div className="space-y-1">
                      {analysis.similar_conditions.map((cond, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between text-xs"
                        >
                          <span className="text-slate-600 dark:text-slate-300">
                            {cond.condition_label}
                          </span>
                          <span
                            className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                              cond.similarity_score >= 0.8
                                ? "bg-success-100 text-success-700"
                                : cond.similarity_score >= 0.5
                                  ? "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300"
                                  : "bg-slate-100 dark:bg-slate-900 text-slate-500 dark:text-slate-400"
                            }`}
                          >
                            {Math.round(cond.similarity_score * 100)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default ImageUploadSection;
