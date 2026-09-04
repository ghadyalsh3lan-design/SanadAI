import { useEffect, useState } from "react";
import { Upload, Trash2, FileType, Loader2 } from "lucide-react";
import { api, DOC_TYPES, DOC_TYPE_LABEL } from "../api.js";
import { Card, Pill, Button, PageHeader, Banner, SectionTitle } from "../components/ui.jsx";

const COLOR_FOR = {
  proposal: "navy",
  capability: "blue",
  overview: "indigo",
  case_study: "amber",
  cv: "green",
  certification: "rose",
  partner: "indigo",
  policy: "slate",
};

export default function KnowledgeBase() {
  const [docs, setDocs] = useState([]);
  const [docType, setDocType] = useState(DOC_TYPES[0][0]);
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [offline, setOffline] = useState(false);

  const load = () =>
    api
      .getDocuments()
      .then((d) => {
        setDocs(d);
        setOffline(false);
      })
      .catch(() => setOffline(true));

  useEffect(() => {
    load();
  }, []);

  async function handleUpload() {
    if (!files.length) return;
    setBusy(true);
    setError("");
    try {
      for (const f of files) await api.uploadDocument(f, docType);
      setFiles([]);
      await load();
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  }

  async function handleDelete(id) {
    try {
      await api.deleteDocument(id);
      await load();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div>
      <PageHeader
        title="Knowledge base"
        subtitle="Add or remove documents. SanadAI re-learns immediately."
      />
      {offline && (
        <Banner tone="amber" className="mb-5">
          API not reachable — start the backend to manage documents.
        </Banner>
      )}
      {error && (
        <Banner tone="rose" className="mb-5">
          {error}
        </Banner>
      )}

      <Card className="mb-6 p-5">
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
            {busy ? "Indexing…" : `Add ${files.length || ""} file(s) to knowledge base`}
          </Button>
        </div>
      </Card>

      <SectionTitle>Current library — {docs.length} document(s)</SectionTitle>
      <Card className="overflow-hidden">
        {docs.map((d, i) => (
          <div
            key={d.doc_id}
            className={`flex items-center gap-3 px-4 py-3 ${
              i < docs.length - 1 ? "border-b border-slate-100" : ""
            }`}
          >
            <FileType className="h-[18px] w-[18px] text-slate-400" />
            <span className="flex-1 truncate text-sm">{d.filename}</span>
            <Pill color={COLOR_FOR[d.doc_type] || "slate"}>
              {DOC_TYPE_LABEL[d.doc_type] || d.doc_type}
            </Pill>
            <span className="w-16 text-right text-xs text-slate-400">{d.chunk_count} secs</span>
            <button
              onClick={() => handleDelete(d.doc_id)}
              className="text-slate-400 hover:text-rose-600"
              aria-label={`Remove ${d.filename}`}
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        {docs.length === 0 && (
          <div className="px-4 py-6 text-center text-sm text-slate-500">No documents yet.</div>
        )}
      </Card>
    </div>
  );
}
