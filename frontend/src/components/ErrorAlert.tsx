import { useEffect, useState } from "react";

interface ErrorAlertProps {
  message: string;
  /** If provided, shows a "Retry" button */
  onRetry?: () => void;
  /** If provided, shows a dismiss (X) button */
  onDismiss?: () => void;
  /** Auto-dismiss after N seconds (default: no auto-dismiss) */
  autoDismissSeconds?: number;
}

export default function ErrorAlert({
  message,
  onRetry,
  onDismiss,
  autoDismissSeconds,
}: ErrorAlertProps) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (!autoDismissSeconds) return;
    const timer = setTimeout(() => {
      setVisible(false);
      onDismiss?.();
    }, autoDismissSeconds * 1000);
    return () => clearTimeout(timer);
  }, [autoDismissSeconds, onDismiss]);

  if (!visible) return null;

  return (
    <div
      className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3"
      role="alert"
    >
      {/* Icon */}
      <svg
        className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-500"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth={1.5}
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"
        />
      </svg>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-sm text-amber-800">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-2 rounded-md bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800 transition-colors hover:bg-amber-200"
          >
            Retry
          </button>
        )}
      </div>

      {/* Dismiss */}
      {onDismiss && (
        <button
          onClick={() => {
            setVisible(false);
            onDismiss();
          }}
          className="flex-shrink-0 rounded p-0.5 text-amber-400 transition-colors hover:text-amber-600"
          aria-label="Dismiss"
        >
          <svg
            className="h-4 w-4"
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
      )}
    </div>
  );
}
