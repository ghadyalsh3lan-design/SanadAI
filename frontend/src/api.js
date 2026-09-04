// API client for the SanadAI FastAPI backend.
const BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function request(path, opts) {
  const res = await fetch(BASE + path, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new Error(detail);
  }
  return res.json();
}

// POST a report/draft and download the .docx the server returns.
async function downloadDocx(path, payload) {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  const match = cd.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : "document.docx";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const api = {
  base: BASE,
  getStats: () => request("/kb/stats"),
  getDocuments: () => request("/kb/documents"),
  uploadDocument: (file, docType) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("doc_type", docType);
    return request("/kb/documents", { method: "POST", body: fd });
  },
  deleteDocument: (docId) => request(`/kb/documents/${docId}`, { method: "DELETE" }),
  query: (question, k = 3, verify = false, doc_types = null, sources = null, include_rfps = false, history = null) =>
    request("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, k, verify, doc_types, sources, include_rfps, history }),
    }),
  evaluate: (question, answer, k = 3, doc_types = null, sources = null, include_rfps = false) =>
    request("/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, answer, k, doc_types, sources, include_rfps }),
    }),
  // Chat history
  getChatSessions: () => request("/chat/sessions"),
  getChatSession: (id) => request(`/chat/sessions/${id}`),
  saveChatSession: (messages, session_id = null, title = null) =>
    request("/chat/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, session_id, title }),
    }),
  deleteChatSession: (id) => request(`/chat/sessions/${id}`, { method: "DELETE" }),
  // Admin — LLM provider control
  getAdminLlm: () => request("/admin/llm"),
  setAdminLlm: (payload) =>
    request("/admin/llm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  testAdminLlm: () => request("/admin/llm/test", { method: "POST" }),
  analyzeRfp: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request("/analyze-rfp", { method: "POST", body: fd });
  },
  // Incoming RFP library — saved files selectable on the Analyze page
  getRfps: () => request("/rfps"),
  uploadRfp: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request("/rfps", { method: "POST", body: fd });
  },
  deleteRfp: (filename) =>
    request(`/rfps/${encodeURIComponent(filename)}`, { method: "DELETE" }),
  analyzeSavedRfp: (filename) =>
    request(`/rfps/${encodeURIComponent(filename)}/analyze`, { method: "POST" }),
  draftSavedRfp: (filename) =>
    request(`/rfps/${encodeURIComponent(filename)}/draft`, { method: "POST" }),
  regenerateSavedSection: (filename, sectionTitle) => {
    const fd = new FormData();
    fd.append("section_title", sectionTitle);
    return request(`/rfps/${encodeURIComponent(filename)}/draft/section`, {
      method: "POST",
      body: fd,
    });
  },
  draftProposal: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request("/draft-proposal", { method: "POST", body: fd });
  },
  exportAnalysis: (report) => downloadDocx("/export/analysis", report),
  exportProposal: (draft) => downloadDocx("/export/proposal", draft),
  // Workspace bid tracker
  getWorkspaceBids: () => request("/workspace/bids"),
  addWorkspaceBid: (rfp_filename, status = "analyzed", analysis = null) =>
    request("/workspace/bids", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rfp_filename, status, analysis }),
    }),
  updateWorkspaceBid: (bidId, status) =>
    request(`/workspace/bids/${bidId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }),
  deleteWorkspaceBid: (bidId) =>
    request(`/workspace/bids/${bidId}`, { method: "DELETE" }),
  // Per-section proposal regeneration
  regenerateSection: (file, sectionTitle) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("section_title", sectionTitle);
    return request("/draft-proposal/section", { method: "POST", body: fd });
  },
};

// UI buckets — value must match the backend's doc_type keys.
export const DOC_TYPES = [
  ["proposal", "Past proposals & RFP responses"],
  ["capability", "Capability statements"],
  ["case_study", "Case studies / project sheets"],
  ["cv", "CVs / resumes"],
  ["certification", "Certifications (ISO, partner)"],
  ["partner", "Partners / vendors / teaming"],
  ["overview", "Company overview & boilerplate"],
  ["policy", "Policies (security, QA, HSE)"],
];

export const DOC_TYPE_LABEL = Object.fromEntries(DOC_TYPES);
