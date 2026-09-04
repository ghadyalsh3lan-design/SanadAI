import { useEffect, useState } from "react";
import { Files, LayoutGrid, MessagesSquare, Cpu, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { api } from "../api.js";
import { Card, Pill, Button, PageHeader, Banner, IconTile, SectionTitle } from "../components/ui.jsx";

const PROVIDER_LABELS = {
  groq: "Groq",
  anthropic: "Anthropic",
  openai: "OpenAI",
  gemini: "Google Gemini",
  local: "Local (OpenAI-compatible)",
};

export default function Admin() {
  const [cfg, setCfg] = useState(null);
  const [metrics, setMetrics] = useState({ documents: 0, sections: 0, sessions: 0 });
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [localUrl, setLocalUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  function applyConfig(c) {
    setCfg(c);
    setProvider(c.provider);
    setModel(c.model || "");
    setLocalUrl(c.local_base_url || "");
  }

  function load() {
    api.getAdminLlm().then(applyConfig).catch((e) => setError(e.message));
    Promise.all([api.getStats(), api.getChatSessions()])
      .then(([s, sessions]) =>
        setMetrics({ documents: s.documents, sections: s.sections, sessions: sessions.length })
      )
      .catch(() => {});
  }

  useEffect(load, []);

  async function save() {
    setSaving(true);
    setError("");
    setSaved(false);
    setTestResult(null);
    try {
      const updated = await api.setAdminLlm({
        provider,
        model: model || null,
        local_base_url: provider === "local" ? localUrl || null : null,
      });
      applyConfig(updated);
      setSaved(true);
    } catch (e) {
      setError(e.message);
    }
    setSaving(false);
  }

  async function test() {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await api.testAdminLlm());
    } catch (e) {
      setTestResult({ ok: false, error: e.message });
    }
    setTesting(false);
  }

  if (!cfg) {
    return (
      <div>
        <PageHeader title="Admin" subtitle="System administration and LLM control." />
        {error ? <Banner tone="rose">{error}</Banner> : <Card className="p-10 text-center text-sm text-slate-400">Loading…</Card>}
      </div>
    );
  }

  const dirty = provider !== cfg.provider || (model || "") !== (cfg.model || "") ||
    (provider === "local" && (localUrl || "") !== (cfg.local_base_url || ""));

  const METRIC_TILES = [
    { label: "Documents registered", value: metrics.documents, icon: Files, color: "blue" },
    { label: "Vector store chunks", value: metrics.sections, icon: LayoutGrid, color: "indigo" },
    { label: "Conversation sessions", value: metrics.sessions, icon: MessagesSquare, color: "green" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="System Administration"
        subtitle="Monitor system health and swap the active LLM provider on the fly."
      />

      {error && <Banner tone="rose">{error}</Banner>}

      {/* Metrics */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {METRIC_TILES.map((m) => (
          <Card key={m.label} className="p-4">
            <IconTile color={m.color} className="mb-3">
              <m.icon className="h-[18px] w-[18px]" />
            </IconTile>
            <div className="text-2xl font-semibold leading-none">{m.value}</div>
            <div className="mt-1 text-xs text-slate-500">{m.label}</div>
          </Card>
        ))}
      </div>

      {/* LLM provider */}
      <Card className="p-5">
        <SectionTitle icon={Cpu}>LLM provider</SectionTitle>
        <p className="mb-3 text-xs text-slate-400">
          Runtime only — changes apply immediately and revert to .env on server restart.
          API keys are managed in .env, not here.
        </p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {cfg.providers.map((p) => {
            const keyed = cfg.configured[p];
            const active = provider === p;
            return (
              <button
                key={p}
                onClick={() => setProvider(p)}
                className={`flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5 text-left transition ${
                  active ? "border-navy bg-navy-tint" : "border-slate-200 hover:bg-slate-50"
                }`}
              >
                <div>
                  <div className="text-sm font-medium text-slate-800">{PROVIDER_LABELS[p] || p}</div>
                  <div className="text-xs text-slate-400">
                    {cfg.default_models[p] ? `default: ${cfg.default_models[p]}` : "model set by server"}
                  </div>
                </div>
                <Pill color={keyed ? "green" : "rose"}>{keyed ? "key set" : "no key"}</Pill>
              </button>
            );
          })}
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Model</label>
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={cfg.default_models[provider] || "(server default)"}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </div>
          {provider === "local" && (
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Local API URL</label>
              <input
                value={localUrl}
                onChange={(e) => setLocalUrl(e.target.value)}
                placeholder="http://localhost:11434/v1"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </div>
          )}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button onClick={save} disabled={saving || !dirty}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {saved && !dirty ? "Saved ✓" : "Save changes"}
          </Button>
          <Button variant="secondary" onClick={test} disabled={testing}>
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Cpu className="h-4 w-4" />}
            Test connection
          </Button>
        </div>

        {testResult && (
          <div className="mt-3">
            {testResult.ok ? (
              <Banner tone="blue">
                <span className="inline-flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4" />
                  Connected — {testResult.provider}
                  {testResult.model ? ` · ${testResult.model}` : ""}
                </span>
              </Banner>
            ) : (
              <Banner tone="rose">
                <span className="inline-flex items-start gap-2">
                  <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                  <span>Failed: {testResult.error}</span>
                </span>
              </Banner>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
