import { useState } from "react";
import { Upload, Loader2, CircleCheck } from "lucide-react";
import { api, DOC_TYPES } from "../api.js";
import { Card, Button, Banner } from "../components/ui.jsx";

export default function Setup({ onDone }) {
  const [docType, setDocType] = useState(DOC_TYPES[0][0]);
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [added, setAdded] = useState(0);
  const [error, setError] = useState("");

  async function handleUpload() {
    if (!files.length) return;
    setBusy(true);
    setError("");
    try {
      let n = added;
      for (const f of files) {
        await api.uploadDocument(f, docType);
        n++;
      }
      setAdded(n);
      setFiles([]);
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="mx-auto max-w-2xl px-6 py-12">
        <div className="mb-8 flex items-center gap-3">
          <img src="/download.png" alt="SanadAI" className="h-11 w-11 rounded-xl object-contain" />
          <div>
            <div className="text-xl font-semibold leading-tight">SanadAI</div>
            <div className="text-sm text-slate-400">سند · proposal co-pilot</div>
          </div>
        </div>

        <h1 className="text-2xl font-semibold text-slate-900">Let's build your knowledge base</h1>
        <p className="mt-2 leading-relaxed text-slate-600">
          Upload your company's past work so SanadAI can ground every answer. The more you
          add — proposals, capability statements, case studies, CVs, certifications,
          company overview — the better and more grounded the results.
        </p>

        {added > 0 && (
          <Banner tone="blue" className="mt-5">
            <span className="inline-flex items-center gap-2">
              <CircleCheck className="h-4 w-4" /> {added} document(s) added so far.
            </span>
          </Banner>
        )}
        {error && (
          <Banner tone="rose" className="mt-5">
            {error}
          </Banner>
        )}

        <Card className="mt-6 p-5">
          <label className="mb-1 block text-sm font-medium text-slate-700">Document type</label>
          <select
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          >
            {DOC_TYPES.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>

          <label className="mb-1 mt-4 block text-sm font-medium text-slate-700">Files</label>
          <input
            type="file"
            multiple
            accept=".pdf,.docx,.pptx,.md,.txt"
            onChange={(e) => setFiles(Array.from(e.target.files))}
            className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-navy-tint file:px-4 file:py-2 file:text-sm file:font-medium file:text-navy hover:file:bg-blue-100"
          />

          <div className="mt-4">
            <Button onClick={handleUpload} disabled={!files.length || busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              {busy ? "Indexing…" : `Add ${files.length || ""} file(s)`}
            </Button>
          </div>
        </Card>

        {added > 0 && (
          <div className="mt-6">
            <Button onClick={onDone}>Explore SanadAI →</Button>
          </div>
        )}
      </div>
    </div>
  );
}
