import { useEffect, useState } from "react";
import { PenLine, Loader2, Download, RefreshCw, Upload, FileText } from "lucide-react";
import { api } from "../api.js";
import { Card, Pill, Button, PageHeader, Banner, Markdown } from "../components/ui.jsx";

function toMarkdown(draft) {
  let md = `# ${draft.title}\n\n*Drafted from: ${draft.rfp_filename}*\n\n`;
  for (const s of draft.sections) {
    md += `## ${s.title}\n\n${s.content}\n\n`;
    if (s.sources?.length) {
      const names = [...new Set(s.sources.map((x) => x.source))];
      md += `*Sources: ${names.join(", ")}*\n\n`;
    }
  }
  return md;
}

export default function Draft() {
  const [rfps, setRfps] = useState([]);
  const [selected, setSelected] = useState(""); // filename of the RFP to draft from
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState("");
  // Per-section regeneration state — keyed by section title.
  const [regenerating, setRegenerating] = useState({});

  function loadRfps() {
    api
      .getRfps()
      .then(setRfps)
      .catch(() => setRfps([]));
  }

  useEffect(loadRfps, []);

  async function handleUpload(e) {
    const file = e.target.files[0];
    e.target.value = ""; // allow re-selecting the same file later
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const added = await api.uploadRfp(file);
      loadRfps();
      setSelected(added.filename); // auto-select the freshly uploaded RFP
    } catch (err) {
      setError(err.message);
    }
    setUploading(false);
  }

  async function run() {
    if (!selected) return;
    setBusy(true);
    setError("");
    setDraft(null);
    try {
      setDraft(await api.draftSavedRfp(selected));
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  }

  async function regenerate(sectionTitle) {
    if (!selected || regenerating[sectionTitle]) return;
    setRegenerating((prev) => ({ ...prev, [sectionTitle]: true }));
    try {
      const newSection = await api.regenerateSavedSection(selected, sectionTitle);
      setDraft((prev) => ({
        ...prev,
        sections: prev.sections.map((s) =>
          s.title === sectionTitle ? newSection : s
        ),
      }));
    } catch (e) {
      setError(`Failed to regenerate "${sectionTitle}": ${e.message}`);
      setTimeout(() => setError(""), 5000);
    }
    setRegenerating((prev) => ({ ...prev, [sectionTitle]: false }));
  }

  function downloadMarkdown() {
    const blob = new Blob([toMarkdown(draft)], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = draft.rfp_filename.replace(/\.[^.]+$/, "") + "_proposal.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  const grounded = draft?.sections.filter((s) => s.grounded).length ?? 0;

  return (
    <div>
      <PageHeader
        title="Draft a response"
        subtitle="A grounded first draft, section by section. Always review before submission."
      />
      <Card className="p-5">
        <div className="mb-1 flex items-center justify-between">
          <label className="text-sm font-medium text-slate-700">
            Select an incoming RFP to draft from
          </label>
          <label className="inline-flex cursor-pointer items-center gap-1.5 text-sm font-medium text-navy hover:underline">
            {uploading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            {uploading ? "Uploading…" : "Upload RFP"}
            <input
              type="file"
              accept=".pdf,.docx,.pptx,.md,.txt"
              onChange={handleUpload}
              disabled={uploading}
              className="hidden"
            />
          </label>
        </div>

        {rfps.length === 0 ? (
          <p className="mt-2 text-sm text-slate-400">
            No RFPs saved yet. Upload one to get started.
          </p>
        ) : (
          <div className="mt-2 space-y-1.5">
            {rfps.map((r) => (
              <label
                key={r.filename}
                className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 transition ${
                  selected === r.filename
                    ? "border-navy bg-navy-tint"
                    : "border-slate-200 hover:bg-slate-50"
                }`}
              >
                <input
                  type="radio"
                  name="rfp"
                  checked={selected === r.filename}
                  onChange={() => setSelected(r.filename)}
                  className="accent-navy"
                />
                <FileText className="h-4 w-4 flex-shrink-0 text-slate-400" />
                <span className="flex-1 truncate text-sm text-slate-700">{r.filename}</span>
                <span className="flex-shrink-0 text-xs text-slate-400">{r.size_kb} KB</span>
              </label>
            ))}
          </div>
        )}

        <div className="mt-4">
          <Button onClick={run} disabled={!selected || busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <PenLine className="h-4 w-4" />}
            {busy ? "Drafting…" : "Generate draft"}
          </Button>
        </div>
      </Card>

      {error && (
        <Banner tone="rose" className="mt-5">
          {error}
        </Banner>
      )}

      {draft && (
        <div className="mt-6">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex gap-2">
              <Pill color="navy">{draft.sections.length} sections</Pill>
              <Pill color="green">{grounded} grounded</Pill>
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => api.exportProposal(draft)}>
                <Download className="h-4 w-4" /> Word
              </Button>
              <Button variant="secondary" onClick={downloadMarkdown}>
                <Download className="h-4 w-4" /> Markdown
              </Button>
            </div>
          </div>
          <div className="space-y-4">
            {draft.sections.map((sec, i) => (
              <Card key={i} className="p-5">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-semibold">{sec.title}</h3>
                    <Pill color={sec.grounded ? "green" : "amber"}>
                      {sec.grounded ? "grounded" : "review"}
                    </Pill>
                  </div>
                  <Button
                    variant="ghost"
                    className="px-2 py-1 text-xs"
                    onClick={() => regenerate(sec.title)}
                    disabled={!selected || !!regenerating[sec.title]}
                  >
                    {regenerating[sec.title] ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <RefreshCw className="h-3 w-3" />
                    )}
                    {regenerating[sec.title] ? "Regenerating…" : "Regenerate"}
                  </Button>
                </div>
                <Markdown className="text-slate-800">{sec.content}</Markdown>
                {sec.sources?.length > 0 && (
                  <div className="mt-3 text-xs text-slate-500">
                    Sources: {[...new Set(sec.sources.map((x) => x.source))].join(" · ")}
                  </div>
                )}
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
