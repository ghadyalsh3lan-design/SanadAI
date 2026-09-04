import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Files,
  LayoutGrid,
  ClipboardList,
  Trophy,
  Folder,
  Plus,
  FileText,
  FileType,
} from "lucide-react";
import { api, DOC_TYPE_LABEL } from "../api.js";
import { Card, Pill, IconTile, Button, Banner, SectionTitle } from "../components/ui.jsx";

const DEMO_STATS = {
  documents: 6,
  sections: 198,
  last_updated: "2026-06-14",
  strength: [
    { doc_type: "proposal", count: 1 },
    { doc_type: "capability", count: 4 },
    { doc_type: "case_study", count: 0 },
    { doc_type: "cv", count: 0 },
    { doc_type: "certification", count: 0 },
    { doc_type: "partner", count: 0 },
    { doc_type: "overview", count: 1 },
    { doc_type: "policy", count: 0 },
  ],
};
const DEMO_DOCS = [
  { doc_id: "d1", filename: "Jouf University Proposal by IBTech v2.0.docx", doc_type: "proposal", chunk_count: 159 },
  { doc_id: "d2", filename: "IBTech_AI_ML_Capability.md", doc_type: "capability", chunk_count: 10 },
  { doc_id: "d3", filename: "IBTech_Company_Overview_Sectors.md", doc_type: "overview", chunk_count: 10 },
];

const SAMPLE_BIDS = [
  { name: "Jouf University — Managed IT", status: "Drafting", color: "amber" },
  { name: "CMH26 — LMS Requirements", status: "Reviewing", color: "blue" },
  { name: "HA SQL Database — P56PN25083", status: "Won", color: "green" },
];

const STATUS_COLOR = {
  analyzing: "amber", analyzed: "blue", drafting: "amber",
  drafted: "indigo", reviewing: "amber", won: "green", lost: "slate",
};

const METRIC_TILE = ["blue", "indigo", "amber", "green"];
const PILL_FOR_TYPE = { proposal: "navy", capability: "blue", overview: "indigo" };

function Ring({ percent }) {
  const r = 35;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - percent / 100);
  return (
    <svg width="86" height="86" viewBox="0 0 86 86" className="flex-shrink-0">
      <circle cx="43" cy="43" r={r} fill="none" stroke="#EEF0F2" strokeWidth="9" />
      <circle
        cx="43"
        cy="43"
        r={r}
        fill="none"
        stroke="#1E3A8A"
        strokeWidth="9"
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={offset}
        transform="rotate(-90 43 43)"
      />
      <text x="43" y="48" textAnchor="middle" fontSize="17" fontWeight="500" fill="#1E3A8A">
        {percent}%
      </text>
    </svg>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(DEMO_STATS);
  const [docs, setDocs] = useState(DEMO_DOCS);
  const [live, setLive] = useState(false);
  const [workspaceBids, setWorkspaceBids] = useState([]);
  const [bidsLive, setBidsLive] = useState(false);

  useEffect(() => {
    Promise.all([api.getStats(), api.getDocuments()])
      .then(([s, d]) => {
        setStats(s);
        setDocs(d);
        setLive(true);
      })
      .catch(() => setLive(false));
    api.getWorkspaceBids()
      .then((b) => { setWorkspaceBids(b); setBidsLive(true); })
      .catch(() => {});
  }, []);

  const totalCats = stats.strength.length || 8;
  const coveredCats = stats.strength.filter((c) => c.count > 0).length;
  const coverage = Math.round((coveredCats / totalCats) * 100);
  const covered = stats.strength.filter((c) => c.count > 0);
  const thinCount = totalCats - coveredCats;

  // Bid pipeline stats, derived from live workspace data.
  const DECIDED = ["won", "lost"];
  const activeBids = workspaceBids.filter((b) => !DECIDED.includes(b.status));
  const wonCount = workspaceBids.filter((b) => b.status === "won").length;
  const lostCount = workspaceBids.filter((b) => b.status === "lost").length;
  const decidedCount = wonCount + lostCount;
  const winRate = decidedCount ? Math.round((wonCount / decidedCount) * 100) : null;

  const metrics = [
    { label: "Documents", value: stats.documents, icon: Files },
    { label: "Sections", value: stats.sections, icon: LayoutGrid },
    {
      label: "Active bids",
      value: bidsLive ? activeBids.length : SAMPLE_BIDS.length,
      icon: ClipboardList,
    },
    {
      label: "Win rate",
      value: bidsLive ? (winRate === null ? "—" : `${winRate}%`) : "68%",
      icon: Trophy,
    },
  ];

  return (
    <div>
      {!live && (
        <Banner tone="amber" className="mb-5">
          Showing sample data — start the API (<code>uvicorn src.api.main:app --reload</code>) to go live.
        </Banner>
      )}

      <div className="mb-5 flex items-center justify-between gap-4 rounded-2xl border-l-4 border-gold bg-navy-tint px-5 py-4">
        <div>
          <div className="text-lg font-semibold text-navy-deep">Welcome back, Osama</div>
          <div className="text-sm text-navy">
            {bidsLive
              ? `${activeBids.length} active ${activeBids.length === 1 ? "bid" : "bids"} · ${wonCount} won · ${lostCount} lost`
              : "3 active bids · 2 deadlines this week"}
          </div>
        </div>
        <Button onClick={() => navigate("/analyze")}>
          <Plus className="h-4 w-4" /> New analysis
        </Button>
      </div>

      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {metrics.map((m, i) => (
          <Card key={m.label} className="p-4">
            <IconTile color={METRIC_TILE[i]} className="mb-3">
              <m.icon className="h-[18px] w-[18px]" />
            </IconTile>
            <div className="text-2xl font-semibold leading-none">{m.value}</div>
            <div className="mt-1 text-xs text-slate-500">{m.label}</div>
          </Card>
        ))}
      </div>

      <div className="mb-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <div className="mb-3 text-sm font-medium text-slate-700">Knowledge base coverage</div>
          <div className="flex items-center gap-4">
            <Ring percent={coverage} />
            <div className="min-w-0">
              <div className="mb-2 text-xs text-slate-500">
                {coveredCats} of {totalCats} categories covered
              </div>
              <div className="flex flex-wrap gap-1.5">
                {covered.map((c) => (
                  <Pill key={c.doc_type} color={PILL_FOR_TYPE[c.doc_type] || "blue"}>
                    {DOC_TYPE_LABEL[c.doc_type]?.split(" ")[0] || c.doc_type}
                  </Pill>
                ))}
                {thinCount > 0 && <Pill color="slate">+{thinCount} thin</Pill>}
              </div>
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <SectionTitle right={bidsLive ? null : <Pill color="amber">preview</Pill>}>
            Active bids
          </SectionTitle>
          {(() => {
            const display = bidsLive
              ? workspaceBids.slice(0, 5).map((b) => ({
                  name: b.rfp_filename,
                  status: b.status.charAt(0).toUpperCase() + b.status.slice(1),
                  color: STATUS_COLOR[b.status] || "slate",
                }))
              : SAMPLE_BIDS;
            return display.length === 0 ? (
              <p className="py-4 text-center text-xs text-slate-400">
                No bids tracked — analyze an RFP and save it to bids.
              </p>
            ) : (
              <div className="flex flex-col">
                {display.map((b, i) => (
                  <div
                    key={b.name + i}
                    className={`flex items-center gap-3 py-2.5 ${
                      i < display.length - 1 ? "border-b border-slate-100" : ""
                    }`}
                  >
                    <FileText className="h-[17px] w-[17px] text-slate-400" />
                    <span className="flex-1 truncate text-sm">{b.name}</span>
                    <Pill color={b.color}>{b.status}</Pill>
                  </div>
                ))}
              </div>
            );
          })()}
        </Card>
      </div>

      <SectionTitle
        icon={Folder}
        right={
          <button
            onClick={() => navigate("/knowledge-base")}
            className="text-xs font-medium text-navy hover:underline"
          >
            Manage library
          </button>
        }
      >
        Recent documents
      </SectionTitle>
      <Card className="overflow-hidden">
        {docs.slice(0, 5).map((d, i) => (
          <div
            key={d.doc_id}
            className={`flex items-center gap-3 px-4 py-3 ${
              i < Math.min(docs.length, 5) - 1 ? "border-b border-slate-100" : ""
            }`}
          >
            <IconTile color={PILL_FOR_TYPE[d.doc_type] || "blue"} className="!h-8 !w-8">
              <FileType className="h-4 w-4" />
            </IconTile>
            <span className="flex-1 truncate text-sm">{d.filename}</span>
            <Pill color={PILL_FOR_TYPE[d.doc_type] || "blue"}>
              {DOC_TYPE_LABEL[d.doc_type] || d.doc_type}
            </Pill>
            <span className="w-12 text-right text-xs text-slate-400">{d.chunk_count}</span>
          </div>
        ))}
        {docs.length === 0 && (
          <div className="px-4 py-6 text-center text-sm text-slate-500">
            No documents yet — add some in the Knowledge base.
          </div>
        )}
      </Card>
    </div>
  );
}
