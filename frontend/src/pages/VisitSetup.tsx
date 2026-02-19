import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { createSession, searchFHIRPatients, importFHIRPatient } from "../api";
import type { FHIRPatient, FHIRImportResult, VisitType } from "../types";

interface AudioDevice {
  deviceId: string;
  label: string;
}

export default function VisitSetup() {
  const navigate = useNavigate();

  // Form state
  const [patientName, setPatientName] = useState("");
  const [visitType, setVisitType] = useState<VisitType>("follow_up");
  const [chiefComplaint, setChiefComplaint] = useState("");

  // FHIR patient search state
  const [fhirResults, setFhirResults] = useState<FHIRPatient[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [fhirLoading, setFhirLoading] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState<FHIRPatient | null>(null);
  const [importResult, setImportResult] = useState<FHIRImportResult | null>(null);
  const [importLoading, setImportLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Audio state
  const [micPermission, setMicPermission] = useState<
    "prompt" | "granted" | "denied"
  >("prompt");
  const [audioDevices, setAudioDevices] = useState<AudioDevice[]>([]);
  const [selectedDevice, setSelectedDevice] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enumerateDevices = useCallback(async () => {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const mics = devices
        .filter((d) => d.kind === "audioinput")
        .map((d) => ({
          deviceId: d.deviceId,
          label: d.label || `Microphone ${d.deviceId.slice(0, 8)}`,
        }));
      setAudioDevices(mics);
      if (mics.length > 0 && !selectedDevice) {
        setSelectedDevice(mics[0].deviceId);
      }
    } catch {
      console.error("Failed to enumerate audio devices");
    }
  }, [selectedDevice]);

  // FHIR patient search with debounce
  const handlePatientNameChange = (value: string) => {
    setPatientName(value);
    // Clear selection if user edits after selecting
    if (selectedPatient) {
      setSelectedPatient(null);
      setImportResult(null);
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (value.length < 2) {
      setFhirResults([]);
      setShowDropdown(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setFhirLoading(true);
      try {
        const results = await searchFHIRPatients(value);
        setFhirResults(results);
        setShowDropdown(results.length > 0);
      } catch {
        // FHIR server may not be configured — silently ignore
        setFhirResults([]);
        setShowDropdown(false);
      } finally {
        setFhirLoading(false);
      }
    }, 300);
  };

  const handleSelectPatient = async (patient: FHIRPatient) => {
    setSelectedPatient(patient);
    setPatientName(patient.name);
    setShowDropdown(false);
    setImportLoading(true);
    try {
      const result = await importFHIRPatient(patient.id);
      setImportResult(result);
    } catch {
      setImportResult(null);
    } finally {
      setImportLoading(false);
    }
  };

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const requestMicPermission = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
      setMicPermission("granted");
      await enumerateDevices();
    } catch {
      setMicPermission("denied");
    }
  };

  useEffect(() => {
    // Check existing permission state
    navigator.permissions
      ?.query({ name: "microphone" as PermissionName })
      .then((result) => {
        if (result.state === "granted") {
          setMicPermission("granted");
          enumerateDevices();
        } else if (result.state === "denied") {
          setMicPermission("denied");
        }
      })
      .catch(() => {
        // permissions API not available in all browsers
      });
  }, [enumerateDevices]);

  const handleStartRecording = async () => {
    if (micPermission !== "granted") {
      setError("Microphone permission is required to start recording.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const session = await createSession(
        visitType,
        {
          name: patientName || undefined,
          chief_complaint: chiefComplaint || undefined,
          fhir_id: selectedPatient?.id,
          age: importResult?.patient.age ?? undefined,
        },
        importResult
          ? {
              medications: importResult.medications,
              allergies: importResult.allergies.map((a) => a.substance),
              conditions: importResult.conditions,
            }
          : undefined,
      );
      navigate(`/session/${session.id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create session",
      );
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-slate-100 dark:bg-slate-950">
      {/* Header */}
      <nav className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-8 py-4 dark:border-slate-700 dark:bg-slate-900">
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-2 text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
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
              d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18"
            />
          </svg>
          <span className="text-sm font-medium">Back</span>
        </button>
        <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Visit Setup</span>
        <div className="w-16" /> {/* spacer */}
      </nav>

      {/* Form */}
      <main className="flex flex-1 items-start justify-center px-6 py-12">
        <div className="w-full max-w-lg">
          <h1 className="mb-1 text-2xl font-bold text-slate-900 dark:text-slate-100">
            Set up your visit
          </h1>
          <p className="mb-8 text-sm text-slate-500 dark:text-slate-400">
            Provide optional context to help Open Attend generate more accurate
            notes.
          </p>

          <div className="space-y-6">
            {/* Patient name with FHIR search */}
            <div ref={dropdownRef} className="relative">
              <label htmlFor="patientName" className="label">
                Patient Name{" "}
                <span className="font-normal text-slate-400">(optional — type to search EHR)</span>
              </label>
              <div className="relative">
                <input
                  id="patientName"
                  type="text"
                  value={patientName}
                  onChange={(e) => handlePatientNameChange(e.target.value)}
                  onFocus={() => fhirResults.length > 0 && setShowDropdown(true)}
                  placeholder="e.g., John Smith"
                  className="input-field"
                  autoComplete="off"
                />
                {fhirLoading && (
                  <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2">
                    <svg className="h-4 w-4 animate-spin text-slate-400" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  </div>
                )}
              </div>

              {/* FHIR search dropdown */}
              {showDropdown && fhirResults.length > 0 && (
                <ul className="absolute z-20 mt-1 max-h-48 w-full overflow-auto rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800">
                  {fhirResults.map((p) => (
                    <li key={p.id}>
                      <button
                        type="button"
                        onClick={() => handleSelectPatient(p)}
                        className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors hover:bg-slate-50 dark:hover:bg-slate-700"
                      >
                        <span className="font-medium text-slate-900 dark:text-slate-100">{p.name}</span>
                        {p.age != null && (
                          <span className="text-xs text-slate-500 dark:text-slate-400">{p.age}y</span>
                        )}
                        {p.gender && (
                          <span className="text-xs text-slate-500 dark:text-slate-400">{p.gender}</span>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              {/* FHIR import preview card */}
              {selectedPatient && (
                <div className="mt-3 rounded-lg border border-clinical-200 bg-clinical-50 p-4 dark:border-clinical-800 dark:bg-clinical-950">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm font-semibold text-clinical-800 dark:text-clinical-200">
                      EHR Data — {selectedPatient.name}
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedPatient(null);
                        setImportResult(null);
                      }}
                      className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                    >
                      Clear
                    </button>
                  </div>
                  {importLoading ? (
                    <p className="text-xs text-slate-500">Loading patient data...</p>
                  ) : importResult ? (
                    <div className="space-y-2">
                      {importResult.medications.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-slate-600 dark:text-slate-400">Medications</p>
                          <p className="text-xs text-slate-500">
                            {importResult.medications.map((m) => m.name).join(", ")}
                          </p>
                        </div>
                      )}
                      {importResult.allergies.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-alert-600">Allergies</p>
                          <p className="text-xs text-alert-500">
                            {importResult.allergies.map((a) => a.substance).join(", ")}
                          </p>
                        </div>
                      )}
                      {importResult.conditions.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-slate-600 dark:text-slate-400">Active Conditions</p>
                          <p className="text-xs text-slate-500">
                            {importResult.conditions.join(", ")}
                          </p>
                        </div>
                      )}
                      {importResult.medications.length === 0 &&
                        importResult.allergies.length === 0 &&
                        importResult.conditions.length === 0 && (
                          <p className="text-xs text-slate-500">No medications, allergies, or conditions on file.</p>
                        )}
                    </div>
                  ) : (
                    <p className="text-xs text-alert-500">Failed to load patient data.</p>
                  )}
                </div>
              )}
            </div>

            {/* Visit type */}
            <div>
              <label htmlFor="visitType" className="label">
                Visit Type
              </label>
              <select
                id="visitType"
                value={visitType}
                onChange={(e) => setVisitType(e.target.value as VisitType)}
                className="input-field"
              >
                <option value="follow_up">Follow-Up</option>
                <option value="new_patient">New Patient</option>
                <option value="urgent">Urgent / Walk-In</option>
              </select>
            </div>

            {/* Chief complaint */}
            <div>
              <label htmlFor="chiefComplaint" className="label">
                Chief Complaint{" "}
                <span className="font-normal text-slate-400">(optional)</span>
              </label>
              <textarea
                id="chiefComplaint"
                value={chiefComplaint}
                onChange={(e) => setChiefComplaint(e.target.value)}
                placeholder="e.g., Chest pain on exertion for 2 weeks"
                rows={3}
                className="input-field resize-none"
              />
            </div>

            {/* Divider */}
            <div className="border-t border-slate-200 pt-6 dark:border-slate-700">
              <h2 className="mb-4 text-base font-semibold text-slate-900 dark:text-slate-100">
                Audio Configuration
              </h2>

              {/* Mic permission */}
              {micPermission === "prompt" && (
                <div className="mb-4 rounded-lg border border-clinical-200 bg-clinical-50 p-4 dark:border-clinical-800 dark:bg-clinical-950">
                  <div className="mb-3 flex items-start gap-3">
                    <svg
                      className="mt-0.5 h-5 w-5 flex-shrink-0 text-clinical-600"
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
                    <div>
                      <p className="text-sm font-medium text-clinical-800 dark:text-clinical-200">
                        Microphone access required
                      </p>
                      <p className="mt-1 text-xs text-clinical-600">
                        Open Attend needs microphone access to transcribe the
                        doctor-patient conversation. Audio is processed in real
                        time and is not stored.
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={requestMicPermission}
                    className="btn-primary w-full !py-2 text-sm"
                  >
                    Allow Microphone Access
                  </button>
                </div>
              )}

              {micPermission === "denied" && (
                <div className="mb-4 rounded-lg border border-alert-200 bg-alert-50 p-4 dark:border-alert-700 dark:bg-alert-500/10">
                  <p className="text-sm font-medium text-alert-800">
                    Microphone access denied
                  </p>
                  <p className="mt-1 text-xs text-alert-600">
                    Please enable microphone access in your browser settings and
                    reload the page.
                  </p>
                </div>
              )}

              {micPermission === "granted" && (
                <div className="mb-4 flex items-center gap-2 text-sm text-success-700">
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
                      d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
                    />
                  </svg>
                  Microphone access granted
                </div>
              )}

              {/* Device selector */}
              {audioDevices.length > 0 && (
                <div>
                  <label htmlFor="audioDevice" className="label">
                    Audio Input
                  </label>
                  <select
                    id="audioDevice"
                    value={selectedDevice}
                    onChange={(e) => setSelectedDevice(e.target.value)}
                    className="input-field"
                  >
                    {audioDevices.map((device) => (
                      <option key={device.deviceId} value={device.deviceId}>
                        {device.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {/* Error */}
            {error && (
              <div className="rounded-lg border border-alert-200 bg-alert-50 px-4 py-3 text-sm text-alert-700">
                {error}
              </div>
            )}

            {/* Start Recording */}
            <button
              onClick={handleStartRecording}
              disabled={micPermission !== "granted" || isSubmitting}
              className="btn-primary w-full !py-4 text-lg font-bold"
            >
              {isSubmitting ? (
                <span className="flex items-center gap-2">
                  <svg
                    className="h-5 w-5 animate-spin"
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
                  Creating session...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <svg
                    className="h-6 w-6"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <circle cx="12" cy="12" r="8" />
                  </svg>
                  Start Recording
                </span>
              )}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
