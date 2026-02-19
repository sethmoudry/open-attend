import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getSettings, updateSettings, testLLMConnection, getSystemResources } from "../api";
import { useTheme } from "../ThemeContext";
import type { LLMProviderConfig, ClassifierConfig, SystemResources, LLMTestResult, LLMProvider } from "../types";

const PROVIDER_PRESETS: Record<string, Partial<LLMProviderConfig>> = {
  ollama: { base_url: "http://localhost:11434/v1", model: "medgemma:4b-it", api_key: "" },
  vllm_local: { base_url: "http://localhost:8080/v1", model: "google/medgemma-27b-text-it", api_key: "" },
  openrouter: { base_url: "https://openrouter.ai/api/v1", model: "google/gemini-2.5-flash-lite-preview-09-2025", api_key: "" },
  vertex_ai: { base_url: "", model: "google/medgemma-27b-text-it", api_key: "" },
  custom: { base_url: "", model: "", api_key: "" },
};

const PROVIDER_LABELS: Record<string, { label: string; desc: string }> = {
  ollama: { label: "Ollama (Local)", desc: "Run MedGemma 4B on your laptop — no GPU needed" },
  vllm_local: { label: "vLLM (Local GPU)", desc: "Local GPU server running vLLM" },
  openrouter: { label: "OpenRouter (Cloud)", desc: "Cloud API — requires API key" },
  vertex_ai: { label: "Vertex AI (GCP)", desc: "Google Cloud managed endpoints" },
  custom: { label: "Custom", desc: "Manual endpoint configuration" },
};

export default function SettingsPage() {
  const navigate = useNavigate();
  const { theme, toggle: toggleTheme } = useTheme();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  // LLM config
  const [llm, setLlm] = useState<LLMProviderConfig>({
    provider: "vllm_local", base_url: "http://localhost:8080/v1", model: "google/medgemma-27b-text-it", api_key: "",
  });
  const [visionLlm, setVisionLlm] = useState<LLMProviderConfig>({
    provider: "vllm_local", base_url: "http://localhost:8080/v1", model: "google/medgemma-1.5-4b-it", api_key: "",
  });
  const [showVision, setShowVision] = useState(false);

  // Test connection
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<LLMTestResult | null>(null);

  // Resources
  const [resources, setResources] = useState<SystemResources | null>(null);

  // Classifiers
  const [classifiers, setClassifiers] = useState<ClassifierConfig[]>([]);

  useEffect(() => {
    Promise.all([
      getSettings().catch(() => null),
      getSystemResources().catch(() => null),
    ]).then(([settings, res]) => {
      if (settings) {
        setLlm(settings.llm);
        setVisionLlm(settings.vision_llm);
        setClassifiers(settings.classifiers);
      }
      if (res) setResources(res);
      setLoading(false);
    });
  }, []);

  const handleProviderChange = (provider: LLMProvider) => {
    const preset = PROVIDER_PRESETS[provider];
    setLlm((prev) => ({ ...prev, provider, ...preset }));
    // Auto-set vision to same provider for ollama
    if (provider === "ollama") {
      setVisionLlm((prev) => ({ ...prev, provider, base_url: preset.base_url!, model: "medgemma:4b-it" }));
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testLLMConnection();
      setTestResult(result);
    } catch {
      setTestResult({ status: "error", latency_ms: 0, model: llm.model, base_url: llm.base_url, error: "Connection failed" });
    }
    setTesting(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveMsg("");
    try {
      await updateSettings({ llm, vision_llm: visionLlm, classifiers });
      setSaveMsg("Settings saved");
      setTimeout(() => setSaveMsg(""), 3000);
    } catch {
      setSaveMsg("Save failed");
    }
    setSaving(false);
  };

  const toggleClassifier = (id: string) => {
    setClassifiers((prev) =>
      prev.map((c) => (c.id === id ? { ...c, enabled: !c.enabled } : c))
    );
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 dark:bg-slate-900">
        <div className="text-slate-400">Loading settings...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      {/* Header */}
      <header className="border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/dashboard")}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 hover:text-slate-600 dark:hover:text-slate-300"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
              </svg>
            </button>
            <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Settings</h1>
          </div>
          <button
            onClick={toggleTheme}
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
            title="Toggle theme"
          >
            {theme === "dark" ? (
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" /></svg>
            ) : (
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z" /></svg>
            )}
          </button>
        </div>
      </header>

      <div className="mx-auto max-w-3xl space-y-6 px-6 py-8">
        {/* Section 1: LLM Provider */}
        <div className="card">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-1">LLM Provider</h2>
          <p className="text-xs text-slate-400 dark:text-slate-500 mb-4">Configure the language model used for clinical reasoning</p>

          {/* Provider selector */}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 mb-4">
            {(Object.keys(PROVIDER_LABELS) as LLMProvider[]).map((key) => (
              <button
                key={key}
                onClick={() => handleProviderChange(key)}
                className={`rounded-lg border p-3 text-left transition-colors ${
                  llm.provider === key
                    ? "border-clinical-500 bg-clinical-50 dark:bg-clinical-900/20 dark:border-clinical-400"
                    : "border-slate-200 dark:border-slate-600 hover:border-slate-300 dark:hover:border-slate-500"
                }`}
              >
                <div className={`text-xs font-medium ${llm.provider === key ? "text-clinical-700 dark:text-clinical-300" : "text-slate-700 dark:text-slate-300"}`}>
                  {PROVIDER_LABELS[key].label}
                </div>
                <div className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">{PROVIDER_LABELS[key].desc}</div>
              </button>
            ))}
          </div>

          {/* Ollama info callout */}
          {llm.provider === "ollama" && (
            <div className="rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 px-3 py-2 mb-4">
              <p className="text-xs text-blue-700 dark:text-blue-300 font-medium mb-1">Laptop Deployment</p>
              <p className="text-[10px] text-blue-600 dark:text-blue-400 leading-relaxed">
                Install Ollama (brew install ollama), then pull the model: <code className="bg-blue-100 dark:bg-blue-800 px-1 rounded">ollama pull medgemma:4b-it</code>.
                Recommended: Apple M1+ with 16GB RAM or x86 with 16GB RAM. No GPU required.
              </p>
            </div>
          )}

          {/* Config fields */}
          <div className="space-y-3">
            <div>
              <label className="label">Base URL</label>
              <input
                type="text"
                value={llm.base_url}
                onChange={(e) => setLlm((p) => ({ ...p, base_url: e.target.value }))}
                className="input-field"
                placeholder="http://localhost:8080/v1"
              />
            </div>
            <div>
              <label className="label">Model</label>
              <input
                type="text"
                value={llm.model}
                onChange={(e) => setLlm((p) => ({ ...p, model: e.target.value }))}
                className="input-field"
                placeholder="google/medgemma-27b-text-it"
              />
            </div>
            {(llm.provider === "openrouter" || llm.provider === "vertex_ai" || llm.provider === "custom") && (
              <div>
                <label className="label">API Key</label>
                <input
                  type="password"
                  value={llm.api_key}
                  onChange={(e) => setLlm((p) => ({ ...p, api_key: e.target.value }))}
                  className="input-field"
                  placeholder="sk-..."
                />
              </div>
            )}
          </div>

          {/* Test connection */}
          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={handleTest}
              disabled={testing}
              className="btn-secondary flex items-center gap-2 text-xs"
            >
              {testing ? (
                <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5.636 18.364a9 9 0 0 1 0-12.728m12.728 0a9 9 0 0 1 0 12.728M9.172 15.828a4.5 4.5 0 0 1 0-6.364m5.656 0a4.5 4.5 0 0 1 0 6.364" />
                </svg>
              )}
              Test Connection
            </button>
            {testResult && (
              <span className={`text-xs font-medium ${testResult.status === "ok" ? "text-emerald-600 dark:text-emerald-400" : "text-red-500"}`}>
                {testResult.status === "ok"
                  ? `Connected (${testResult.latency_ms}ms)`
                  : `Failed: ${testResult.error}`}
              </span>
            )}
          </div>

          {/* Vision LLM toggle */}
          <div className="mt-4 border-t border-slate-100 dark:border-slate-700 pt-4">
            <button
              onClick={() => setShowVision(!showVision)}
              className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
            >
              <svg className={`h-3 w-3 transition-transform ${showVision ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
              </svg>
              Vision LLM (image/lab analysis)
            </button>
            {showVision && (
              <div className="mt-3 space-y-3 pl-5">
                <div>
                  <label className="label">Base URL</label>
                  <input
                    type="text"
                    value={visionLlm.base_url}
                    onChange={(e) => setVisionLlm((p) => ({ ...p, base_url: e.target.value }))}
                    className="input-field"
                  />
                </div>
                <div>
                  <label className="label">Model</label>
                  <input
                    type="text"
                    value={visionLlm.model}
                    onChange={(e) => setVisionLlm((p) => ({ ...p, model: e.target.value }))}
                    className="input-field"
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Section 2: System Resources */}
        <div className="card">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-1">System Resources</h2>
          <p className="text-xs text-slate-400 dark:text-slate-500 mb-4">Hardware and loaded models</p>

          {resources ? (
            <div className="space-y-3">
              {/* GPU */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500 dark:text-slate-400">GPU</span>
                <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  {resources.gpu ? `${resources.gpu.name} (${resources.gpu.vram_total_gb}GB VRAM)` : "Not detected"}
                </span>
              </div>

              {/* RAM */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-slate-500 dark:text-slate-400">RAM</span>
                  <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                    {resources.ram.used_gb}GB / {resources.ram.total_gb}GB ({resources.ram.percent}%)
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-slate-200 dark:bg-slate-700">
                  <div
                    className={`h-1.5 rounded-full ${resources.ram.percent > 90 ? "bg-red-500" : resources.ram.percent > 70 ? "bg-amber-500" : "bg-emerald-500"}`}
                    style={{ width: `${resources.ram.percent}%` }}
                  />
                </div>
              </div>

              {/* Disk */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500 dark:text-slate-400">Disk</span>
                <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  {resources.disk.free_gb}GB free / {resources.disk.total_gb}GB
                </span>
              </div>

              {/* CPU */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500 dark:text-slate-400">CPU</span>
                <span className="text-xs font-medium text-slate-700 dark:text-slate-300">{resources.cpu_percent}%</span>
              </div>

              {/* Loaded models */}
              {resources.loaded_models.length > 0 && (
                <div>
                  <span className="text-xs text-slate-500 dark:text-slate-400">Loaded Models</span>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {resources.loaded_models.map((m) => (
                      <span key={m} className="rounded-full bg-emerald-100 dark:bg-emerald-900/30 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:text-emerald-300">
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-400">Resource information unavailable</p>
          )}
        </div>

        {/* Section 3: Classifiers */}
        <div className="card">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-1">Classifiers</h2>
          <p className="text-xs text-slate-400 dark:text-slate-500 mb-2">Drop-in ready for pre-trained audio and image classifiers</p>
          <div className="rounded-lg bg-slate-50 dark:bg-slate-700/30 border border-slate-200 dark:border-slate-600 px-3 py-2 mb-4">
            <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-relaxed">
              The classifier registry is a pluggable architecture — add any trained classifier that maps HeAR audio embeddings or medical images to diagnostic labels. Classifiers produce structured predictions that the LLM interprets in clinical context. Install a classifier package, enable it here, and it runs automatically during analysis.
            </p>
          </div>

          {/* Audio classifiers */}
          {classifiers.filter((c) => c.type === "audio").length > 0 && (
            <div className="mb-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">Audio Classifiers</h3>
              <div className="rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 px-3 py-2 mb-3">
                <p className="text-[10px] text-amber-700 dark:text-amber-300">
                  Drop-in ready: HeAR extracts 512-dim health audio embeddings. Any trained classifier that maps these embeddings to diagnostic labels (cough detection, respiratory sounds, etc.) can be plugged in. The LLM interprets classifier predictions in clinical context.
                </p>
              </div>
              <div className="space-y-2">
                {classifiers.filter((c) => c.type === "audio").map((c) => (
                  <div key={c.id} className="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-600 px-3 py-2.5">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-slate-700 dark:text-slate-300">{c.name}</span>
                        {!c.installed && (
                          <span className="rounded bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 text-[9px] font-medium text-slate-500 dark:text-slate-400">Not installed</span>
                        )}
                        <span className="rounded-full bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 text-[9px] text-slate-500 dark:text-slate-400">
                          {c.labels.length} labels
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400 mt-0.5">{c.description}</p>
                    </div>
                    <button
                      onClick={() => toggleClassifier(c.id)}
                      disabled={!c.installed}
                      className={`relative h-5 w-9 rounded-full transition-colors ${
                        c.enabled && c.installed ? "bg-clinical-500" : "bg-slate-300 dark:bg-slate-600"
                      } ${!c.installed ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
                    >
                      <span className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white transition-transform shadow-sm ${c.enabled && c.installed ? "translate-x-4" : ""}`} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Image classifiers */}
          {classifiers.filter((c) => c.type === "image").length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">Image Classifiers</h3>
              <div className="rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 px-3 py-2 mb-3">
                <p className="text-[10px] text-amber-700 dark:text-amber-300">
                  Drop-in ready: any trained image classifier (chest X-ray pathology, skin lesion, retinal scan, etc.) can be plugged in via the registry. Classifiers provide structured diagnostic predictions that the LLM interprets alongside MedGemma vision analysis.
                </p>
              </div>
              <div className="space-y-2">
                {classifiers.filter((c) => c.type === "image").map((c) => (
                  <div key={c.id} className="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-600 px-3 py-2.5">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-slate-700 dark:text-slate-300">{c.name}</span>
                        {c.installed ? (
                          <span className="rounded bg-emerald-100 dark:bg-emerald-900/30 px-1.5 py-0.5 text-[9px] font-medium text-emerald-600 dark:text-emerald-400">Installed</span>
                        ) : (
                          <span className="rounded bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 text-[9px] font-medium text-slate-500 dark:text-slate-400">Not installed</span>
                        )}
                        <span className="rounded-full bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 text-[9px] text-slate-500 dark:text-slate-400">
                          {c.labels.length} labels
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400 mt-0.5">{c.description}</p>
                    </div>
                    <button
                      onClick={() => toggleClassifier(c.id)}
                      disabled={!c.installed}
                      className={`relative h-5 w-9 rounded-full transition-colors ${
                        c.enabled && c.installed ? "bg-clinical-500" : "bg-slate-300 dark:bg-slate-600"
                      } ${!c.installed ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
                    >
                      <span className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white transition-transform shadow-sm ${c.enabled && c.installed ? "translate-x-4" : ""}`} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Save button */}
        <div className="flex items-center justify-between">
          <span className={`text-xs font-medium ${saveMsg === "Settings saved" ? "text-emerald-600 dark:text-emerald-400" : saveMsg ? "text-red-500" : "text-transparent"}`}>
            {saveMsg || "."}
          </span>
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn-primary px-6"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>
      </div>
    </div>
  );
}
