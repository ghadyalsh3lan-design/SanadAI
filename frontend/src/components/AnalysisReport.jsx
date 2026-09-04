import { useState } from "react";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
} from "lucide-react";
import { Card, Pill, SectionTitle, Markdown } from "./ui.jsx";

// Shared rendering for a pre-bid analysis report. Used interactively on the
// Analyze page (via BidRecommendation) and read-only in the Workspace viewer.

export const COVERAGE = {
  fully_covered: ["Fully covered", "green"],
  partially_covered: ["Partial", "amber"],
  not_covered: ["Not covered", "rose"],
};
export const SEVERITY = {
  blocker: ["Blocker", "rose"],
  important: ["Important", "amber"],
  nice_to_clarify: ["Nice to clarify", "green"],
};
export const COVERAGE_ORDER = ["fully_covered", "partially_covered", "not_covered"];
export const SEVERITY_ORDER = ["blocker", "important", "nice_to_clarify"];

const COMPLY_LABEL = {
  yes: ["Comply", "green"],
  partial: ["Partial", "amber"],
  no: ["No Bid", "rose"],
};

const RECOMMENDATION = {
  Bid: { icon: CheckCircle2, banner: "bg-emerald-50 border-emerald-200", text: "text-emerald-700" },
  "Bid with Risks": { icon: AlertTriangle, banner: "bg-amber-50 border-amber-200", text: "text-amber-700" },
  "No Bid": { icon: XCircle, banner: "bg-rose-50 border-rose-200", text: "text-rose-700" },
};

const DETAIL_AREAS = [
  ["submission_deadline", "Submission deadline"],
  ["project_scope", "Project scope"],
  ["eligibility", "Eligibility"],
  ["required_documents", "Required documents"],
  ["exclusion_criteria", "Exclusion criteria"],
  ["technical_capability", "Technical capability"],
  ["relevant_experience", "Relevant experience"],
  ["resource_availability", "Resource availability"],
];

// LLM-generated fields sometimes contain literal <br> tags; turn them into real
// line breaks so Markdown renders cleanly instead of showing the raw tag.
export function cleanText(s) {
  return (s || "").replace(/<br\s*\/?>/gi, "\n");
}

export function BidRecommendation({ rec }) {
  const style = RECOMMENDATION[rec.recommendation] || RECOMMENDATION["No Bid"];
  const Icon = style.icon;
  const areas = DETAIL_AREAS.filter(([key]) => rec.detailed_analysis?.[key]);
  return (
    <div className="mb-6">
      <div className={`rounded-2xl border p-5 ${style.banner}`}>
        <div className="flex items-center gap-3">
          <Icon className={`h-7 w-7 ${style.text}`} />
          <div>
            <div className={`text-xl font-semibold ${style.text}`}>{rec.recommendation}</div>
            <div className="text-xs text-slate-500">
              Confidence: {Math.round((rec.confidence ?? 0) * 100)}%
            </div>
          </div>
        </div>
        {rec.summary && <Markdown className="mt-3 text-slate-700">{rec.summary}</Markdown>}
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {rec.strengths?.length > 0 && (
          <Card className="p-4">
            <div className="mb-2 text-sm font-medium text-emerald-700">Strengths</div>
            <ul className="space-y-1 text-sm text-slate-700">
              {rec.strengths.map((x, i) => (
                <li key={i} className="flex gap-2">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-500" />
                  <span>{x}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}
        {rec.risks?.length > 0 && (
          <Card className="p-4">
            <div className="mb-2 text-sm font-medium text-amber-700">Risks</div>
            <ul className="space-y-1 text-sm text-slate-700">
              {rec.risks.map((x, i) => (
                <li key={i} className="flex gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-500" />
                  <span>{x}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      {rec.missing_requirements?.length > 0 && (
        <Card className="mt-4 p-4">
          <div className="mb-2 text-sm font-medium text-rose-700">Missing requirements</div>
          <ul className="space-y-1 text-sm text-slate-700">
            {rec.missing_requirements.map((x, i) => (
              <li key={i} className="flex gap-2">
                <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-rose-500" />
                <span>{x}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {areas.length > 0 && (
        <div className="mt-4">
          <SectionTitle>Detailed assessment</SectionTitle>
          <div className="space-y-2">
            {areas.map(([key, label]) => (
              <details key={key} className="rounded-lg border border-slate-200 bg-white p-3">
                <summary className="cursor-pointer text-sm font-medium text-slate-700">
                  {label}
                </summary>
                <Markdown className="mt-2 text-slate-600">
                  {rec.detailed_analysis[key]}
                </Markdown>
              </details>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Full read-only report viewer (recommendation + coverage + questions) used in
// the Workspace. Tabs keep it compact.
export function AnalysisReport({ report }) {
  const [tab, setTab] = useState(report.bid_recommendation ? "recommendation" : "coverage");
  const s = report.coverage_summary || { fully_covered: 0, partially_covered: 0, not_covered: 0 };
  const reqs = [...(report.requirements || [])].sort(
    (a, b) => COVERAGE_ORDER.indexOf(a.coverage) - COVERAGE_ORDER.indexOf(b.coverage)
  );
  const qs = [...(report.clarifying_questions || [])].sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
  );

  return (
    <div>
      <div className="mb-5 flex gap-1 border-b border-slate-200">
        {[
          ["recommendation", "Recommendation", !!report.bid_recommendation],
          ["coverage", `Coverage (${reqs.length})`, true],
          ["questions", `Questions (${qs.length})`, true],
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

      {tab === "recommendation" && report.bid_recommendation && (
        <BidRecommendation rec={report.bid_recommendation} />
      )}

      {tab === "coverage" && (
        <div>
          <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
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
          <div className="space-y-2">
            {reqs.map((r, i) => {
              const [label, color] = COVERAGE[r.coverage] || [r.coverage, "slate"];
              const comply = r.comply ? COMPLY_LABEL[r.comply] : null;
              return (
                <Card key={i} className="p-4">
                  <div className="mb-1 flex items-start justify-between gap-3">
                    <Markdown className="min-w-0 flex-1 text-sm font-medium">
                      {cleanText(r.requirement)}
                    </Markdown>
                    <div className="flex flex-shrink-0 gap-1.5">
                      {comply && <Pill color={comply[1]}>{comply[0]}</Pill>}
                      {r.relevance != null && (
                        <Pill color="blue">{Math.round(r.relevance * 100)}% match</Pill>
                      )}
                      <Pill color={color}>{label}</Pill>
                    </div>
                  </div>
                  <Markdown className="text-xs text-slate-500">
                    {cleanText(r.evidence) + (r.source ? ` · ${r.source}` : "")}
                  </Markdown>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {tab === "questions" && (
        <div className="space-y-2">
          {qs.map((q, i) => {
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
  );
}
