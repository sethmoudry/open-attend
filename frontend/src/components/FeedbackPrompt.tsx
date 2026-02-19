import { useState } from "react";
import { submitFeedback } from "../api";

interface FeedbackPromptProps {
  sessionId: string;
}

export default function FeedbackPrompt({ sessionId }: FeedbackPromptProps) {
  const [rating, setRating] = useState(0);
  const [hoveredStar, setHoveredStar] = useState(0);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (rating === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitFeedback(sessionId, rating, comment);
      setSubmitted(true);
    } catch {
      setError("Could not submit feedback. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-5 text-center">
        <svg
          className="mx-auto mb-2 h-8 w-8 text-emerald-500"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
          />
        </svg>
        <p className="text-sm font-medium text-emerald-800">
          Thank you for your feedback!
        </p>
        <p className="mt-1 text-xs text-emerald-600">
          Your input helps us improve Scribe.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <h3 className="mb-1 text-sm font-semibold text-slate-900">
        How was this session?
      </h3>
      <p className="mb-4 text-xs text-slate-400">
        Rate the quality of the generated documentation.
      </p>

      {/* Star rating */}
      <div className="mb-4 flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((star) => {
          const filled = star <= (hoveredStar || rating);
          return (
            <button
              key={star}
              onClick={() => setRating(star)}
              onMouseEnter={() => setHoveredStar(star)}
              onMouseLeave={() => setHoveredStar(0)}
              className="rounded p-0.5 transition-colors hover:bg-slate-100"
              aria-label={`Rate ${star} star${star > 1 ? "s" : ""}`}
            >
              <svg
                className={`h-7 w-7 ${filled ? "text-amber-400" : "text-slate-200"}`}
                fill={filled ? "currentColor" : "none"}
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z"
                />
              </svg>
            </button>
          );
        })}
        {rating > 0 && (
          <span className="ml-2 text-xs text-slate-400">
            {rating}/5
          </span>
        )}
      </div>

      {/* Comment */}
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Any additional comments? (optional)"
        rows={3}
        className="mb-4 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 focus:border-clinical-400 focus:outline-none focus:ring-1 focus:ring-clinical-400"
      />

      {/* Error */}
      {error && (
        <p className="mb-3 text-xs text-amber-600">{error}</p>
      )}

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={rating === 0 || submitting}
        className={`w-full rounded-lg px-4 py-2 text-sm font-semibold transition-colors ${
          rating === 0
            ? "cursor-not-allowed bg-slate-100 text-slate-400"
            : "bg-clinical-600 text-white hover:bg-clinical-700"
        }`}
      >
        {submitting ? "Submitting..." : "Submit Feedback"}
      </button>
    </div>
  );
}
