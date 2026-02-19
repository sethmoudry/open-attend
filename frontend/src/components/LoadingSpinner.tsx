interface LoadingSpinnerProps {
  /** Spinner diameter: sm=16px, md=24px, lg=40px */
  size?: "sm" | "md" | "lg";
  /** Optional label rendered below the spinner */
  label?: string;
  /** Display variant */
  variant?: "inline" | "overlay" | "full-page";
}

const sizeClasses = {
  sm: "h-4 w-4 border-[2px]",
  md: "h-6 w-6 border-2",
  lg: "h-10 w-10 border-[3px]",
} as const;

export default function LoadingSpinner({
  size = "md",
  label,
  variant = "inline",
}: LoadingSpinnerProps) {
  const spinner = (
    <div
      className={`animate-spin rounded-full border-clinical-600 border-t-transparent ${sizeClasses[size]}`}
      role="status"
      aria-label={label ?? "Loading"}
    />
  );

  if (variant === "full-page") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="text-center">
          {spinner}
          {label && (
            <p className="mt-3 text-sm text-slate-500">{label}</p>
          )}
        </div>
      </div>
    );
  }

  if (variant === "overlay") {
    return (
      <div className="flex flex-1 items-center justify-center py-12">
        <div className="text-center">
          {spinner}
          {label && (
            <p className="mt-3 text-sm text-slate-500">{label}</p>
          )}
        </div>
      </div>
    );
  }

  // inline — sits naturally in flow, useful inside buttons
  return (
    <span className="inline-flex items-center gap-2">
      {spinner}
      {label && <span className="text-sm text-slate-500">{label}</span>}
    </span>
  );
}
