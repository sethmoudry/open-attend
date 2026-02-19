import { useCallback, useState } from "react";
import {
  approveSession,
  downloadSOAPPdf,
  downloadPatientSummaryPdf,
  getSOAPText,
} from "../../api";
import type { Session } from "../../types";

interface ExportBarProps {
  session: Session;
  onSessionUpdated?: (session: Session) => void;
  onDiscard?: () => void;
}

export default function ExportBar({
  session,
  onSessionUpdated,
  onDiscard,
}: ExportBarProps) {
  const isApproved = session.soap_note.status === "reviewed";
  const [approving, setApproving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [downloadingSoap, setDownloadingSoap] = useState(false);
  const [downloadingSummary, setDownloadingSummary] = useState(false);

  const handleApprove = useCallback(async () => {
    if (isApproved || approving) return;
    setApproving(true);
    try {
      const updated = await approveSession(session.id);
      onSessionUpdated?.(updated);
    } catch (err) {
      console.error("Failed to approve session:", err);
    } finally {
      setApproving(false);
    }
  }, [session.id, isApproved, approving, onSessionUpdated]);

  const handleDownloadSoap = useCallback(async () => {
    setDownloadingSoap(true);
    try {
      const blob = await downloadSOAPPdf(session.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `soap_note_${session.id.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to download SOAP PDF:", err);
    } finally {
      setDownloadingSoap(false);
    }
  }, [session.id]);

  const handleDownloadSummary = useCallback(async () => {
    setDownloadingSummary(true);
    try {
      const blob = await downloadPatientSummaryPdf(session.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `patient_summary_${session.id.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to download patient summary PDF:", err);
    } finally {
      setDownloadingSummary(false);
    }
  }, [session.id]);

  const handleCopy = useCallback(async () => {
    try {
      const text = await getSOAPText(session.id);
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy SOAP text:", err);
    }
  }, [session.id]);

  return (
    <div className="flex shrink-0 items-center justify-between border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-6 py-3">
      <button
        onClick={onDiscard}
        className="text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:text-slate-300 transition-colors"
      >
        Discard &amp; Start New
      </button>

      <div className="flex items-center gap-2">
        {/* Approve button */}
        <button
          onClick={handleApprove}
          disabled={isApproved || approving}
          className={`flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-semibold transition-colors ${
            isApproved
              ? "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 cursor-default"
              : approving
                ? "bg-clinical-200 text-clinical-500 cursor-wait"
                : "bg-clinical-600 text-white hover:bg-clinical-700"
          }`}
        >
          {isApproved ? (
            <>
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
              </svg>
              Approved
            </>
          ) : approving ? (
            <>
              <div className="h-3 w-3 animate-spin rounded-full border-2 border-clinical-500 border-t-transparent" />
              Approving...
            </>
          ) : (
            "Approve"
          )}
        </button>

        {/* Divider */}
        <div className="mx-1 h-6 w-px bg-slate-200 dark:bg-slate-700" />

        {/* Download SOAP PDF */}
        <button
          onClick={handleDownloadSoap}
          disabled={!isApproved || downloadingSoap}
          title={!isApproved ? "Approve the note first" : "Download SOAP PDF"}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
            !isApproved
              ? "bg-slate-100 dark:bg-slate-900 text-slate-400 dark:text-slate-500 cursor-not-allowed"
              : downloadingSoap
                ? "bg-slate-100 dark:bg-slate-900 text-slate-500 dark:text-slate-400 cursor-wait"
                : "bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-600 hover:bg-slate-50 dark:bg-slate-900"
          }`}
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
          </svg>
          {downloadingSoap ? "Downloading..." : "SOAP PDF"}
        </button>

        {/* Download Patient Summary */}
        <button
          onClick={handleDownloadSummary}
          disabled={!isApproved || downloadingSummary}
          title={!isApproved ? "Approve the note first" : "Download Patient Summary"}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
            !isApproved
              ? "bg-slate-100 dark:bg-slate-900 text-slate-400 dark:text-slate-500 cursor-not-allowed"
              : downloadingSummary
                ? "bg-slate-100 dark:bg-slate-900 text-slate-500 dark:text-slate-400 cursor-wait"
                : "bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-600 hover:bg-slate-50 dark:bg-slate-900"
          }`}
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
          </svg>
          {downloadingSummary ? "Downloading..." : "Patient Summary"}
        </button>

        {/* Copy to Clipboard */}
        <button
          onClick={handleCopy}
          disabled={!isApproved}
          title={!isApproved ? "Approve the note first" : "Copy SOAP text to clipboard"}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
            !isApproved
              ? "bg-slate-100 dark:bg-slate-900 text-slate-400 dark:text-slate-500 cursor-not-allowed"
              : copied
                ? "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300"
                : "bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-600 hover:bg-slate-50 dark:bg-slate-900"
          }`}
        >
          {copied ? (
            <>
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
              </svg>
              Copied!
            </>
          ) : (
            <>
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0 0 13.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 0 1-.75.75H9.75a.75.75 0 0 1-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 0 1-2.25 2.25H6.75A2.25 2.25 0 0 1 4.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 0 1 1.927-.184" />
              </svg>
              Copy to Clipboard
            </>
          )}
        </button>
      </div>
    </div>
  );
}
