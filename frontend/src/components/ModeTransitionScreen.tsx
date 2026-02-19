import { useEffect, useState } from "react";

interface ModeTransitionScreenProps {
  isVisible: boolean;
  onComplete: () => void;
}

interface StepState {
  label: string;
  status: "pending" | "active" | "done";
}

const STEP_LABELS = [
  "Finalizing transcription",
  "Assembling SOAP note",
  "Extracting diagnosis codes",
];

// Minimum display time per step for visual polish (ms)
const STEP_DURATION = 1200;

export default function ModeTransitionScreen({
  isVisible,
  onComplete,
}: ModeTransitionScreenProps) {
  const [steps, setSteps] = useState<StepState[]>(
    STEP_LABELS.map((label) => ({ label, status: "pending" })),
  );
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    if (!isVisible) {
      // Reset when hidden
      setSteps(STEP_LABELS.map((label) => ({ label, status: "pending" })));
      setCurrentStep(0);
      return;
    }

    // Animate through steps
    let stepIndex = 0;

    const advance = () => {
      setSteps((prev) =>
        prev.map((s, i) => {
          if (i < stepIndex) return { ...s, status: "done" };
          if (i === stepIndex) return { ...s, status: "active" };
          return { ...s, status: "pending" };
        }),
      );
      setCurrentStep(stepIndex);
      stepIndex++;

      if (stepIndex <= STEP_LABELS.length) {
        setTimeout(advance, STEP_DURATION);
      } else {
        // All done
        setSteps((prev) => prev.map((s) => ({ ...s, status: "done" })));
        setTimeout(onComplete, 600);
      }
    };

    advance();
  }, [isVisible, onComplete]);

  if (!isVisible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 backdrop-blur-md">
      <div className="mx-4 w-full max-w-sm text-center">
        {/* Animated icon */}
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-clinical-600 shadow-lg shadow-clinical-600/30">
          <svg
            className="h-8 w-8 animate-pulse text-white"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
            />
          </svg>
        </div>

        <h2 className="mb-1 text-lg font-semibold text-white">
          Visit ended
        </h2>
        <p className="mb-8 text-sm text-slate-300">
          Finalizing documentation...
        </p>

        {/* Progress steps */}
        <div className="space-y-3">
          {steps.map((step, i) => (
            <div
              key={i}
              className={`flex items-center gap-3 rounded-lg px-4 py-3 transition-all duration-300 ${
                step.status === "active"
                  ? "bg-white/10"
                  : step.status === "done"
                    ? "bg-white/5"
                    : "bg-transparent"
              }`}
            >
              {/* Status indicator */}
              <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center">
                {step.status === "done" ? (
                  <svg
                    className="h-5 w-5 text-green-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2.5}
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="m4.5 12.75 6 6 9-13.5"
                    />
                  </svg>
                ) : step.status === "active" ? (
                  <svg
                    className="h-5 w-5 animate-spin text-clinical-400"
                    fill="none"
                    viewBox="0 0 24 24"
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
                ) : (
                  <div className="h-2 w-2 rounded-full bg-slate-500" />
                )}
              </div>

              <span
                className={`text-sm font-medium transition-colors duration-300 ${
                  step.status === "done"
                    ? "text-slate-400"
                    : step.status === "active"
                      ? "text-white"
                      : "text-slate-500"
                }`}
              >
                {step.label}
              </span>
            </div>
          ))}
        </div>

        {/* Progress bar */}
        <div className="mt-6 h-1 overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-clinical-500 transition-all duration-700 ease-out"
            style={{
              width: `${((currentStep + 1) / STEP_LABELS.length) * 100}%`,
            }}
          />
        </div>
      </div>
    </div>
  );
}
