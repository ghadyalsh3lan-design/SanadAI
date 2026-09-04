import { useEffect, useState } from "react";
import { Trash2, FileText, Eye, X } from "lucide-react";
import { api } from "../api.js";
import { Card, Pill, PageHeader } from "../components/ui.jsx";
import { AnalysisReport } from "../components/AnalysisReport.jsx";

const STATUS_OPTIONS = [
  "analyzed",
  "drafting",
  "drafted",
  "reviewing",
  "won",
  "lost",
];

const STATUS_COLOR = {
  analyzing: "amber",
  analyzed: "blue",
  drafting: "amber",
  drafted: "indigo",
  reviewing: "amber",
  won: "green",
  lost: "slate",
};

function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function Workspace() {
  const [bids, setBids] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewing, setViewing] = useState(null); // bid whose analysis is open

  async function load() {
    try {
      setBids(await api.getWorkspaceBids());
    } catch {
      setBids([]);
    }
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  async function changeStatus(bidId, status) {
    try {
      await api.updateWorkspaceBid(bidId, status);
      setBids((prev) =>
        prev.map((b) => (b.bid_id === bidId ? { ...b, status } : b))
      );
    } catch {
      // ignore
    }
  }

  async function remove(bidId) {
    try {
      await api.deleteWorkspaceBid(bidId);
      setBids((prev) => prev.filter((b) => b.bid_id !== bidId));
    } catch {
      // ignore
    }
  }

  return (
    <div>
      <PageHeader
        title="Bids workspace"
        subtitle="Track each RFP through the proposal pipeline."
      />

      {loading ? (
        <div className="py-16 text-center text-sm text-slate-400">Loading…</div>
      ) : bids.length === 0 ? (
        <Card className="p-10 text-center text-sm text-slate-500">
          No bids tracked yet. Analyze an RFP and click{" "}
          <strong>Save to bids</strong> to start tracking it here.
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] items-center gap-3 border-b border-slate-100 px-4 py-2 text-xs font-medium text-slate-400">
            <span>RFP</span>
            <span>Added</span>
            <span>Status</span>
            <span />
            <span />
            <span />
          </div>
          {bids.map((b) => (
            <div
              key={b.bid_id}
              className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] items-center gap-3 border-b border-slate-100 px-4 py-3 last:border-0"
            >
              <div className="flex min-w-0 items-center gap-2">
                <FileText className="h-4 w-4 flex-shrink-0 text-slate-400" />
                <span className="truncate text-sm">{b.rfp_filename}</span>
              </div>
              <span className="text-xs text-slate-400">
                {formatDate(b.created_at)}
              </span>
              <select
                value={b.status}
                onChange={(e) => changeStatus(b.bid_id, e.target.value)}
                className="rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-navy"
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>
              <Pill color={STATUS_COLOR[b.status] || "slate"}>{b.status}</Pill>
              <button
                onClick={() => setViewing(b)}
                disabled={!b.analysis}
                className="text-slate-300 transition enabled:hover:text-navy disabled:opacity-30"
                title={b.analysis ? "View analysis" : "No saved analysis"}
              >
                <Eye className="h-4 w-4" />
              </button>
              <button
                onClick={() => remove(b.bid_id)}
                className="text-slate-300 transition hover:text-rose-500"
                title="Remove bid"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </Card>
      )}

      {viewing?.analysis && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 sm:p-8"
          onClick={() => setViewing(null)}
        >
          <div
            className="w-full max-w-3xl rounded-2xl bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-base font-semibold text-slate-900">Analysis</div>
                <div className="truncate text-xs text-slate-400">{viewing.rfp_filename}</div>
              </div>
              <button
                onClick={() => setViewing(null)}
                className="text-slate-400 hover:text-slate-700"
                title="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <AnalysisReport report={viewing.analysis} />
          </div>
        </div>
      )}
    </div>
  );
}
