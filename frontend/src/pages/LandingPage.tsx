import { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function LandingPage() {
  const navigate = useNavigate();
  const [disclaimerAccepted, setDisclaimerAccepted] = useState(false);

  return (
    <div className="flex min-h-screen flex-col">
      {/* Nav */}
      <nav className="flex items-center justify-between border-b border-slate-200 bg-white px-8 py-4">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-clinical-600">
            <svg
              className="h-5 w-5 text-white"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
              />
            </svg>
          </div>
          <span className="text-xl font-bold text-slate-900">Scribe</span>
        </div>
        <span className="text-xs text-slate-400">
          AI Clinical Documentation
        </span>
      </nav>

      {/* Hero */}
      <main className="flex flex-1 flex-col items-center justify-center px-6 py-16">
        <div className="w-full max-w-2xl text-center">
          {/* Badge */}
          <div className="mb-6 inline-flex items-center rounded-full border border-clinical-200 bg-clinical-50 px-4 py-1.5 text-xs font-medium text-clinical-700">
            Powered by MedGemma + MedASR
          </div>

          <h1 className="mb-4 text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
            Clinical notes,{" "}
            <span className="text-clinical-600">written for you.</span>
          </h1>

          <p className="mx-auto mb-10 max-w-lg text-lg text-slate-500">
            Scribe listens to your patient visit, builds structured SOAP notes
            in real time, checks medication interactions, and surfaces clinical
            intelligence -- so you can focus on the patient.
          </p>

          {/* Feature pills */}
          <div className="mb-10 flex flex-wrap justify-center gap-3">
            {[
              "Live Transcription",
              "Real-Time SOAP Drafting",
              "Medication Interaction Checks",
              "Clinical Alerts",
              "ICD-10 / CPT Extraction",
              "Patient Summary Generation",
            ].map((feature) => (
              <span
                key={feature}
                className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 shadow-sm"
              >
                {feature}
              </span>
            ))}
          </div>

          {/* Disclaimer */}
          <div className="mx-auto mb-8 max-w-md rounded-lg border border-slate-200 bg-slate-50 p-4 text-left">
            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={disclaimerAccepted}
                onChange={(e) => setDisclaimerAccepted(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-clinical-600 focus:ring-clinical-500"
              />
              <span className="text-xs leading-relaxed text-slate-600">
                I understand that Scribe is an{" "}
                <strong>AI documentation assistant</strong>, not a diagnostic
                tool. All clinical decisions remain the responsibility of the
                treating physician. Generated notes, codes, and suggestions must
                be reviewed before use. No patient data is stored beyond the
                active session.
              </span>
            </label>
          </div>

          {/* CTAs */}
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <button
              onClick={() => navigate("/setup")}
              disabled={!disclaimerAccepted}
              className="btn-primary min-w-[200px] !px-8 !py-3.5 text-base"
            >
              <svg
                className="mr-2 h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z"
                />
              </svg>
              Start Visit
            </button>

            <button
              onClick={() => navigate("/dashboard")}
              disabled={!disclaimerAccepted}
              className="min-w-[200px] rounded-lg border border-clinical-300 bg-white px-8 py-3.5 text-base font-semibold text-clinical-600 shadow-sm transition-colors hover:bg-clinical-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <svg
                className="mr-2 inline-block h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25ZM13.5 6a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 6v2.25A2.25 2.25 0 0 1 18 10.5h-2.25a2.25 2.25 0 0 1-2.25-2.25V6ZM13.5 15.75a2.25 2.25 0 0 1 2.25-2.25H18a2.25 2.25 0 0 1 2.25 2.25V18A2.25 2.25 0 0 1 18 20.25h-2.25a2.25 2.25 0 0 1-2.25-2.25v-2.25Z"
                />
              </svg>
              Dashboard
            </button>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white px-8 py-4">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>
            Built with Google HAI-DEF models: MedGemma, MedASR, MedSigLIP
          </span>
          <span>Not for clinical use without physician oversight</span>
        </div>
      </footer>
    </div>
  );
}
