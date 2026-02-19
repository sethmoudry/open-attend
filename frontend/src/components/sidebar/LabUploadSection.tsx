import React, { useCallback, useRef, useState } from "react";
import type { LabReport } from "../../types";
import { uploadLabReport } from "../../api";

interface LabUploadSectionProps {
  sessionId: string;
  onLabReport: (report: LabReport) => void;
  labReports?: LabReport[];
  collapsed?: boolean;
  onToggle?: () => void;
}

const FLAG_STYLES: Record<string, string> = {
  normal: "bg-success-100 text-success-700",
  high: "bg-alert-100 text-alert-700",
  low: "bg-amber-100 text-amber-700",
  critical: "bg-red-200 text-red-800 font-bold",
};

export const LabUploadSection: React.FC<LabUploadSectionProps> = ({
  sessionId,
  onLabReport,
  labReports = [],
  collapsed = false,
  onToggle,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [localReports, setLocalReports] = useState<LabReport[]>([]);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // Merge server-polled reports with locally uploaded ones (deduplicated)
  const allReports = [
    ...labReports,
    ...localReports.filter(
      (lr) => !labReports.some((sr) => sr.id === lr.id),
    ),
  ];

  const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp", "application/pdf"];

  const handleFile = useCallback(
    async (file: File) => {
      if (!ACCEPTED_TYPES.includes(file.type)) {
        setError("Please select an image (JPG, PNG) or PDF file.");
        return;
      }

      setError(null);
      setUploading(true);
      setUploadProgress(10);

      // Show preview for images, placeholder for PDFs
      const objectUrl = file.type.startsWith("image/")
        ? URL.createObjectURL(file)
        : null;
      setPreviewUrl(objectUrl);

      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => Math.min(prev + 6, 90));
      }, 500);

      try {
        const result = await uploadLabReport(sessionId, file);
        setUploadProgress(100);
        setLocalReports((prev) => [...prev, result]);
        onLabReport(result);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Upload failed. Try again.",
        );
      } finally {
        clearInterval(progressInterval);
        setTimeout(() => {
          setUploading(false);
          setUploadProgress(0);
          if (objectUrl) URL.revokeObjectURL(objectUrl);
          setPreviewUrl(null);
        }, 500);
      }
    },
    [sessionId, onLabReport],
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
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
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
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
              d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m5.231 13.481L15 17.25m-4.5-15H5.625c-.621 0-1.125.504-1.125 1.125v16.5c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Zm3.75 11.625a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z"
            />
          </svg>
          Lab Reports
          {allReports.length > 0 && (
            <span className="ml-1 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-clinical-100 px-1.5 text-[10px] font-bold text-clinical-700">
              {allReports.length}
            </span>
          )}
        </h3>
        <svg
          className={`h-4 w-4 text-slate-400 transition-transform ${collapsed ? "" : "rotate-180"}`}
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
                ? "border-clinical-400 bg-clinical-50"
                : "border-slate-300 bg-slate-50 hover:border-clinical-300 hover:bg-clinical-50/50"
            } ${uploading ? "pointer-events-none opacity-60" : ""}`}
          >
            {uploading ? (
              <>
                {previewUrl ? (
                  <img
                    src={previewUrl}
                    alt="Uploading preview"
                    className="h-12 w-12 rounded object-cover"
                  />
                ) : (
                  <div className="flex h-12 w-12 items-center justify-center rounded bg-slate-200">
                    <svg
                      className="h-6 w-6 text-slate-400"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={1.5}
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
                      />
                    </svg>
                  </div>
                )}
                <div className="w-full">
                  <div className="mb-1 text-[10px] font-medium text-clinical-600">
                    Processing lab report...
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
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
                  className="h-5 w-5 text-slate-400"
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
                <p className="text-[11px] text-slate-500">
                  Drop lab report or{" "}
                  <span className="font-medium text-clinical-600">browse</span>
                </p>
                <p className="text-[10px] text-slate-400">
                  JPG, PNG, or PDF
                </p>
              </>
            )}
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*;capture=camera,application/pdf"
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

          {/* Report results */}
          {allReports.length === 0 && !uploading ? (
            <p className="text-xs text-slate-400">
              Upload lab reports for AI-powered result extraction.
            </p>
          ) : (
            allReports.map((report) => (
              <div
                key={report.id}
                className="rounded-lg border border-slate-200 bg-white p-2.5"
              >
                {/* Header: lab name + date */}
                <div className="flex items-start gap-2.5">
                  {report.image_url && (
                    <img
                      src={report.image_url}
                      alt="Lab report"
                      className="h-14 w-14 flex-shrink-0 rounded object-cover"
                    />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-slate-700">
                      {report.lab_name || "Lab Report"}
                    </p>
                    {report.date && (
                      <p className="text-[10px] text-slate-400">
                        {report.date}
                      </p>
                    )}
                    <p className="mt-0.5 text-[10px] text-slate-400">
                      {report.results.length} result{report.results.length !== 1 ? "s" : ""} extracted
                    </p>
                  </div>
                </div>

                {/* Lab results table */}
                {report.results.length > 0 && (
                  <div className="mt-2 border-t border-slate-100 pt-2">
                    <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                      Results
                    </p>
                    <div className="space-y-1">
                      {report.results.map((result, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between text-xs"
                        >
                          <span className="text-slate-600">{result.test}</span>
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-slate-700">
                              {result.value} {result.unit}
                            </span>
                            <span
                              className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                                FLAG_STYLES[result.flag] || FLAG_STYLES.normal
                              }`}
                            >
                              {result.flag === "normal" ? "N" : result.flag.toUpperCase()}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                    {report.results.some((r) => r.reference_range) && (
                      <div className="mt-1.5 space-y-0.5">
                        {report.results
                          .filter((r) => r.reference_range)
                          .map((r, idx) => (
                            <p key={idx} className="text-[10px] text-slate-400">
                              {r.test}: ref {r.reference_range}
                            </p>
                          ))}
                      </div>
                    )}
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

export default LabUploadSection;
