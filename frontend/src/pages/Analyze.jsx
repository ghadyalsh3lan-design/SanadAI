import { useEffect, useState } from "react";
import {
  Upload,
  Loader2,
  Download,
  Save,
  FileText,
  Trash2,
  AlertTriangle,
  Clock,
  Target,
  ClipboardCheck,
  Settings,
  Award,
  Users,
  ListChecks,
} from "lucide-react";
import { api } from "../api.js";
import { Card, Pill, Button, PageHeader, Banner, SectionTitle, Markdown } from "../components/ui.jsx";
import {
  BidRecommendation,
  COVERAGE,
  SEVERITY,
  COVERAGE_ORDER,
  SEVERITY_ORDER,
  cleanText,
} from "../components/AnalysisReport.jsx";

// The eight areas every analysis evaluates — shown as an always-available
// reference panel on the page.
const CRITERIA = [
  [Clock, "Submission deadline", "Is there enough time to prepare a strong proposal?"],
  [Target, "Project scope", "Does the work match our areas of expertise?"],
  [ClipboardCheck, "Eligibility criteria", "Do we meet all mandatory requirements?"],
  [FileText, "Required documents", "Can we provide every required document?"],
  [AlertTriangle, "Exclusion factors", "Is there anything that would disqualify us?"],
  [Settings, "Technical capability", "Do we have the technical skills to execute?"],
  [Award, "Relevant experience", "Do we have references and case studies?"],
  [Users, "Resource availability", "Do we have the team and resources available?"],
];

function CriteriaPanel() {
  return (
    <details className="mt-5 rounded-2xl border border-slate-200 bg-white p-4">
      <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-700">
        <ListChecks className="h-4 w-4 text-slate-500" />
        What this analysis evaluates
      </summary>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {CRITERIA.map(([Icon, title, desc]) => (
          <div key={title} className="flex items-start gap-3 rounded-lg border border-slate-100 px-3 py-2">
            <Icon className="mt-0.5 h-[18px] w-[18px] flex-shrink-0 text-navy" />
            <div>
              <div className="text-[13px] font-semibold text-slate-700">{title}</div>
              <div className="mt-0.5 text-xs text-slate-500">{desc}</div>
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}

// Full class names so Tailwind doesn't purge them.
const COMPLY_OPTS = [
  {
    value: "yes",
    label: "Comply",
    active: "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-400",
    idle: "bg-slate-50 text-slate-500 hover:bg-emerald-50 hover:text-emerald-700",
  },
  {
    value: "partial",
    label: "Partial",
    active: "bg-amber-100 text-amber-700 ring-1 ring-amber-400",
    idle: "bg-slate-50 text-slate-500 hover:bg-amber-50 hover:text-amber-700",
  },
  {
    value: "no",
    label: "No Bid",
    active: "bg-rose-100 text-rose-700 ring-1 ring-rose-400",
    idle: "bg-slate-50 text-slate-500 hover:bg-rose-50 hover:text-rose-700",
  },
];

// Persist the analysis across navigation within a tab session.
const SESSION_KEY = "analyze:session";
function loadSession() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY)) || {};
  } catch {
    return {};
  }
}

export default function Analyze() {
  const persisted = loadSession();
  const [rfps, setRfps] = useState([]);
  const [selected, setSelected] = useState(persisted.selected || "");
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState(persisted.report || null);
  const [error, setError] = useState("");
  // Compliance decisions keyed by requirement text (unique per analysis).
  const [comply, setComply] = useState(persisted.comply || {});
  const [saved, setSaved] = useState(false);
  const [savedFilenames, setSavedFilenames] = useState([]); // RFPs already in bids
  const [tab, setTab] = useState(persisted.tab || "recommendation"); // which result category is shown

  function loadRfps() {
    api
      .getRfps()
      .then(setRfps)
      .catch(() => setRfps([]));
  }

  function loadSavedBids() {
    api
      .getWorkspaceBids()
      .then((bids) => setSavedFilenames(bids.map((b) => b.rfp_filename)))
      .catch(() => setSavedFilenames([]));
  }

  useEffect(() => {
    loadRfps();
    loadSavedBids();
  }, []);

  // Save the current analysis to the session so it survives page navigation.
  useEffect(() => {
    sessionStorage.setItem(
      SESSION_KEY,
      JSON.stringify({ selected, report, comply, tab })
    );
  }, [selected, report, comply, tab]);

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

  async function handleDelete(filename) {
    try {
      await api.deleteRfp(filename);
      if (selected === filename) {
        setSelected("");
        setReport(null);
      }
      loadRfps();
    } catch (err) {
      setError(err.message);
    }
  }

  async function run() {
    if (!selected) return;
    setBusy(true);
    setError("");
    setReport(null);
    setComply({});
    setSaved(false);
    try {
      const result = await api.analyzeSavedRfp(selected);
      setReport(result);
      setTab(result.bid_recommendation ? "recommendation" : "coverage");
      setSaved(savedFilenames.includes(result.rfp_filename));
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  }

  function toggleComply(reqText, value) {
    setComply((prev) => ({
      ...prev,
      [reqText]: prev[reqText] === value ? null : value,
    }));
  }

  // Bake the user's compliance decisions into the report before saving/exporting.
  function reportWithCompliance() {
    return {
      ...report,
      requirements: report.requirements.map((r) => ({
        ...r,
        comply: comply[r.requirement] || null,
      })),
    };
  }

  function exportReport() {
    api.exportAnalysis(reportWithCompliance());
  }

  async function saveToWorkspace() {
    if (!report) return;
    try {
      // Backend upserts by filename, so this never creates a duplicate bid —
      // re-saving the same RFP just refreshes its stored analysis.
      await api.addWorkspaceBid(report.rfp_filename, "analyzed", reportWithCompliance());
      setSaved(true);
      setSavedFilenames((prev) =>
        prev.includes(report.rfp_filename) ? prev : [...prev, report.rfp_filename]
      );
    } catch {
      // workspace is optional — fail silently
    }
  }

  const s = report?.coverage_summary;
  const sortedReqs = report
    ? [...report.requirements].sort(
        (a, b) => COVERAGE_ORDER.indexOf(a.coverage) - COVERAGE_ORDER.indexOf(b.coverage)
      )
    : [];
  const sortedQs = report
    ? [...report.clarifying_questions].sort(
        (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
      )
    : [];

  return (
    <div>
      <PageHeader
        title="Analyze an RFP"
        subtitle="Assess bid readiness against your knowledge base."
      />
      <Card className="p-5">
        <div className="mb-1 flex items-center justify-between">
          <label className="text-sm font-medium text-slate-700">
            Select an incoming RFP to analyze
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
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    handleDelete(r.filename);
                  }}
                  className="flex-shrink-0 text-slate-300 hover:text-rose-500"
                  title="Delete RFP"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </label>
            ))}
          </div>
        )}

        <div className="mt-4">
          <Button onClick={run} disabled={!selected || busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            {busy ? "Analyzing…" : "Analyze RFP"}
          </Button>
        </div>
      </Card>

      <CriteriaPanel />

      {error && (
        <Banner tone="rose" className="mt-5">
          {error}
        </Banner>
      )}

      {report && (
        <div className="mt-6">
          {/* Report actions */}
          <div className="mb-4 flex flex-wrap gap-2">
            <Button variant="secondary" onClick={exportReport}>
              <Download className="h-4 w-4" /> Download Word report
            </Button>
            <Button variant="secondary" onClick={saveToWorkspace}>
              <Save className="h-4 w-4" />
              {saved ? "Update saved bid" : "Save to bids"}
            </Button>
          </div>

          {/* Category tabs */}
          <div className="mb-5 flex gap-1 border-b border-slate-200">
            {[
              ["recommendation", "Recommendation", !!report.bid_recommendation],
              ["coverage", `Coverage (${sortedReqs.length})`, true],
              ["questions", `Questions (${sortedQs.length})`, true],
            ]
              .filter(([, , show]) => show)
              .map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition ${
                    tab === key
                      ? "border-navy text-navy"
                      : "border-transparent text-slate-500 hover:text-slate-700"
                  }`}
                >
                  {label}
                </button>
              ))}
          </div>

          {/* Recommendation tab */}
          {tab === "recommendation" && report.bid_recommendation && (
            <BidRecommendation rec={report.bid_recommendation} />
          )}

          {/* Coverage tab */}
          {tab === "coverage" && (
            <div>
              <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                  ["Requirements", s.fully_covered + s.partially_covered + s.not_covered],
                  ["Fully covered", s.fully_covered],
                  ["Partial", s.partially_covered],
                  ["Not covered", s.not_covered],
                ].map(([label, value]) => (
                  <Card key={label} className="p-4">
                    <div className="text-2xl font-semibold">{value}</div>
                    <div className="mt-1 text-xs text-slate-500">{label}</div>
                  </Card>
                ))}
              </div>

              <SectionTitle>Requirement coverage</SectionTitle>
              <p className="mb-3 text-xs text-slate-400">
                Mark each requirement with your compliance decision — included when you export to Word.
              </p>
              <div className="space-y-2">
                {sortedReqs.map((r, i) => {
                  const [label, color] = COVERAGE[r.coverage] || [r.coverage, "slate"];
                  const current = comply[r.requirement];
                  return (
                    <Card key={i} className="p-4">
                      <div className="mb-1 flex items-start justify-between gap-3">
                        <Markdown className="min-w-0 flex-1 text-sm font-medium">
                          {cleanText(r.requirement)}
                        </Markdown>
                        <div className="flex flex-shrink-0 gap-1.5">
                          {r.relevance != null && (
                            <Pill color="blue">{Math.round(r.relevance * 100)}% match</Pill>
                          )}
                          <Pill color={color}>{label}</Pill>
                        </div>
                      </div>
                      <Markdown className="mb-2 text-xs text-slate-500">
                        {cleanText(r.evidence) + (r.source ? ` · ${r.source}` : "")}
                      </Markdown>
                      <div className="flex gap-1">
                        {COMPLY_OPTS.map(({ value, label: btnLabel, active, idle }) => (
                          <button
                            key={value}
                            onClick={() => toggleComply(r.requirement, value)}
                            className={`rounded px-2.5 py-0.5 text-xs font-medium transition ${
                              current === value ? active : idle
                            }`}
                          >
                            {btnLabel}
                          </button>
                        ))}
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>
          )}

          {/* Questions tab */}
          {tab === "questions" && (
            <div className="space-y-2">
              {sortedQs.map((q, i) => {
                const [label, color] = SEVERITY[q.severity] || [q.severity, "slate"];
                return (
                  <div key={i} className="flex items-start gap-3">
                    <Pill color={color} className="flex-shrink-0">
                      {label}
                    </Pill>
                    <span className="text-sm text-slate-700">{q.question}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
