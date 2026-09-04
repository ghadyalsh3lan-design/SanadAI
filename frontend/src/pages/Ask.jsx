import { useEffect, useMemo, useState } from "react";
import {
  Send,
  Loader2,
  BookOpen,
  ShieldCheck,
  SlidersHorizontal,
  MessageSquarePlus,
  Trash2,
  Gauge,
  History,
  Lightbulb,
} from "lucide-react";
import { api, DOC_TYPES, DOC_TYPE_LABEL } from "../api.js";
import { Card, Pill, Button, PageHeader, Banner, Markdown } from "../components/ui.jsx";

// --- LLM-judge metric visualization ----------------------------------------

const METRICS = [
  ["faithfulness", "Faithfulness"],
  ["relevance", "Relevance"],
  ["completeness", "Completeness"],
  ["groundedness", "Groundedness"],
  ["citation_quality", "Citation quality"],
];

function barColor(score) {
  if (score >= 8) return "bg-emerald-500";
  if (score >= 5) return "bg-amber-500";
  return "bg-rose-500";
}

function MetricBar({ label, score }) {
  const pct = Math.max(0, Math.min(10, score)) * 10;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-slate-600">{label}</span>
        <span className="font-medium text-slate-800">{score.toFixed(1)}/10</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${barColor(score)}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function EvaluationPanel({ evaluation }) {
  const { scores, summary, recommendations } = evaluation;
  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-700">
        <Gauge className="h-4 w-4 text-slate-500" /> LLM-as-a-judge evaluation
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {METRICS.map(([key, label]) => (
          <MetricBar key={key} label={label} score={scores[key] ?? 0} />
        ))}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-600">Hallucination</span>
          <Pill color={scores.hallucination ? "rose" : "green"}>
            {scores.hallucination ? "detected" : "none"}
          </Pill>
        </div>
      </div>
      {summary && <p className="mt-4 text-sm text-slate-700">{summary}</p>}
      {recommendations?.length > 0 && (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-slate-500">
          {recommendations.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// --- A single assistant turn ------------------------------------------------

function AssistantMessage({ msg, onEvaluate, evaluating }) {
  if (msg.refused) {
    return <Banner tone="amber">{msg.content}</Banner>;
  }
  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium text-slate-700">Answer</span>
          <Button
            variant="ghost"
            className="px-2 py-1 text-xs"
            onClick={onEvaluate}
            disabled={evaluating}
          >
            {evaluating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Gauge className="h-3 w-3" />}
            {evaluating ? "Evaluating…" : "Evaluate"}
          </Button>
        </div>
        <Markdown className="text-slate-800">{msg.content}</Markdown>
      </Card>

      {msg.sources?.length > 0 && (
        <Card className="p-5">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-700">
            <BookOpen className="h-4 w-4 text-slate-500" /> Sources ({msg.sources.length})
          </div>
          <div className="space-y-3">
            {msg.sources.map((s, i) => (
              <div key={i} className="border-l-2 border-slate-200 pl-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium">
                    {s.source}
                    {s.page ? ` · p.${s.page}` : ""}
                  </div>
                  {s.relevance != null && (
                    <Pill color="blue" className="flex-shrink-0">
                      {Math.round(s.relevance * 100)}% match
                    </Pill>
                  )}
                </div>
                <div className="text-xs text-slate-500">{s.preview}</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {msg.verification && (
        <Card className="p-5">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-700">
            <ShieldCheck className="h-4 w-4 text-slate-500" /> Verification
          </div>
          <div className="flex gap-3">
            <Pill color={msg.verification.faithful ? "green" : "amber"}>
              Faithful: {msg.verification.faithful ? "yes" : "no"}
            </Pill>
            <Pill color={msg.verification.complete ? "green" : "amber"}>
              Complete: {msg.verification.complete ? "yes" : "no"}
            </Pill>
          </div>
        </Card>
      )}

      {msg.evaluation && <EvaluationPanel evaluation={msg.evaluation} />}
    </div>
  );
}

// --- Page -------------------------------------------------------------------

// Starter prompts shown on an empty chat to help users get going.
const SUGGESTIONS = [
  "What is the submission deadline?",
  "Who is the RFP contact?",
  "What are the mandatory eligibility requirements?",
  "What is the scope of work?",
  "What relevant past experience do we have for this RFP?",
];

export default function Ask() {
  const [q, setQ] = useState("");
  const [k, setK] = useState(3);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Conversation
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [evaluating, setEvaluating] = useState({}); // keyed by message index

  // Filters
  const [showFilters, setShowFilters] = useState(false);
  const [docTypes, setDocTypes] = useState([]); // selected categories
  const [docs, setDocs] = useState([]); // KB documents for the document filter
  const [sources, setSources] = useState([]); // selected KB filenames
  const [rfps, setRfps] = useState([]); // incoming RFP files
  const [rfpSel, setRfpSel] = useState([]); // selected RFP filenames

  // History
  const [sessions, setSessions] = useState([]);

  function loadSessions() {
    api.getChatSessions().then(setSessions).catch(() => setSessions([]));
  }

  useEffect(() => {
    api.getDocuments().then(setDocs).catch(() => setDocs([]));
    api.getRfps().then(setRfps).catch(() => setRfps([]));
    loadSessions();
  }, []);

  // [doc_types, merged sources (KB + RFP), include_rfps] — passed to query/evaluate.
  const filterArgs = useMemo(() => {
    const merged = [...sources, ...rfpSel];
    return [
      docTypes.length ? docTypes : null,
      merged.length ? merged : null,
      rfpSel.length > 0,
    ];
  }, [docTypes, sources, rfpSel]);
  const filterCount = docTypes.length + sources.length + rfpSel.length;

  function toggle(list, setList, value) {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  }

  async function persist(nextMessages) {
    try {
      const saved = await api.saveChatSession(nextMessages, sessionId);
      if (!sessionId) setSessionId(saved.session_id);
      loadSessions();
    } catch {
      // saving history is best-effort
    }
  }

  async function ask(text) {
    const question = (typeof text === "string" ? text : q).trim();
    if (!question || busy) return;
    setBusy(true);
    setError("");
    const withUser = [...messages, { role: "user", content: question }];
    setMessages(withUser);
    setQ("");
    try {
      // Send recent turns (text only) so the backend has conversational memory.
      const history = messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content }));
      const res = await api.query(question, k, false, ...filterArgs, history);
      const next = [
        ...withUser,
        {
          role: "assistant",
          content: res.answer,
          sources: res.sources,
          verification: res.verification,
          refused: res.refused,
          // remember the filters/k used, so Evaluate re-retrieves the same context
          meta: {
            k,
            docTypes: filterArgs[0],
            sources: filterArgs[1],
            includeRfps: filterArgs[2],
          },
        },
      ];
      setMessages(next);
      persist(next);
    } catch (e) {
      setError(e.message);
      setMessages(messages); // roll back the optimistic user message
    }
    setBusy(false);
  }

  async function evaluateMessage(index) {
    const msg = messages[index];
    // The question is the preceding user message.
    const question = messages[index - 1]?.content;
    if (!msg || !question || evaluating[index]) return;
    setEvaluating((prev) => ({ ...prev, [index]: true }));
    try {
      const meta = msg.meta || {};
      const evaluation = await api.evaluate(
        question,
        msg.content,
        meta.k ?? k,
        meta.docTypes ?? null,
        meta.sources ?? null,
        meta.includeRfps ?? false
      );
      const next = messages.map((m, i) => (i === index ? { ...m, evaluation } : m));
      setMessages(next);
      persist(next);
    } catch (e) {
      setError(e.message);
    }
    setEvaluating((prev) => ({ ...prev, [index]: false }));
  }

  function newChat() {
    setMessages([]);
    setSessionId(null);
    setError("");
  }

  async function loadSession(id) {
    try {
      const s = await api.getChatSession(id);
      setMessages(s.messages || []);
      setSessionId(s.session_id);
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }

  async function removeSession(id, e) {
    e.stopPropagation();
    try {
      await api.deleteChatSession(id);
      if (id === sessionId) newChat();
      loadSessions();
    } catch {
      // ignore
    }
  }

  return (
    <div>
      <PageHeader
        title="Ask questions"
        subtitle="Grounded answers from your company's past work."
        action={
          <Button variant="secondary" onClick={newChat}>
            <MessageSquarePlus className="h-4 w-4" /> New chat
          </Button>
        }
      />

      <div className="flex gap-6">
        {/* History sidebar */}
        <aside className="hidden w-60 flex-shrink-0 lg:block">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700">
            <History className="h-4 w-4 text-slate-500" /> Chat history
          </div>
          {sessions.length === 0 ? (
            <p className="text-xs text-slate-400">No saved chats yet.</p>
          ) : (
            <div className="space-y-1">
              {sessions.map((s) => (
                <div
                  key={s.session_id}
                  onClick={() => loadSession(s.session_id)}
                  className={`group flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm transition ${
                    s.session_id === sessionId
                      ? "bg-navy-tint text-navy"
                      : "text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  <span className="flex-1 truncate">{s.title}</span>
                  <span className="text-xs text-slate-300">{s.message_count}</span>
                  <button
                    onClick={(e) => removeSession(s.session_id, e)}
                    className="text-slate-300 opacity-0 transition hover:text-rose-500 group-hover:opacity-100"
                    title="Delete chat"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </aside>

        {/* Main column */}
        <div className="min-w-0 flex-1">
          <Card className="p-5">
            <textarea
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask();
              }}
              rows={3}
              placeholder="e.g. What experience do we have with cloud infrastructure?"
              className="w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
            <div className="mt-3 flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-slate-600">
                Sources
                <input
                  type="range"
                  min="1"
                  max="20"
                  value={k}
                  onChange={(e) => setK(+e.target.value)}
                />
                <span className="w-5 font-medium">{k}</span>
              </label>
              <button
                onClick={() => setShowFilters((v) => !v)}
                className={`inline-flex items-center gap-1.5 text-sm font-medium ${
                  filterCount ? "text-navy" : "text-slate-500"
                } hover:underline`}
              >
                <SlidersHorizontal className="h-4 w-4" />
                Filters
                {filterCount > 0 && <Pill color="navy">{filterCount}</Pill>}
              </button>
              <Button onClick={() => ask()} disabled={!q.trim() || busy} className="ml-auto">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Ask
              </Button>
            </div>

            {filterCount === 0 && (
              <p className="mt-2 flex items-center gap-1.5 text-xs text-slate-400">
                <Lightbulb className="h-3.5 w-3.5" />
                Tip: open Filters and select specific documents or an incoming RFP for more focused, higher-quality answers.
              </p>
            )}

            {showFilters && (
              <div className="mt-4 grid gap-4 border-t border-slate-100 pt-4 sm:grid-cols-2">
                <div>
                  <div className="mb-2 text-xs font-medium text-slate-500">Categories</div>
                  <div className="flex flex-wrap gap-1.5">
                    {DOC_TYPES.map(([value, label]) => (
                      <button
                        key={value}
                        onClick={() => toggle(docTypes, setDocTypes, value)}
                        className={`rounded-full px-2.5 py-1 text-xs transition ${
                          docTypes.includes(value)
                            ? "bg-navy text-white"
                            : "bg-slate-50 text-slate-600 hover:bg-slate-100"
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="mb-2 text-xs font-medium text-slate-500">Documents</div>
                  {docs.length === 0 ? (
                    <p className="text-xs text-slate-400">No documents in the knowledge base.</p>
                  ) : (
                    <div className="max-h-40 space-y-1 overflow-y-auto pr-1">
                      {docs.map((d) => (
                        <label
                          key={d.doc_id}
                          className="flex cursor-pointer items-center gap-2 text-xs text-slate-600"
                        >
                          <input
                            type="checkbox"
                            checked={sources.includes(d.filename)}
                            onChange={() => toggle(sources, setSources, d.filename)}
                            className="accent-navy"
                          />
                          <span className="truncate">{d.filename}</span>
                          <span className="ml-auto flex-shrink-0 text-[10px] text-slate-300">
                            {DOC_TYPE_LABEL[d.doc_type] || d.doc_type}
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
                <div className="sm:col-span-2">
                  <div className="mb-2 text-xs font-medium text-slate-500">Incoming RFPs</div>
                  {rfps.length === 0 ? (
                    <p className="text-xs text-slate-400">No incoming RFPs uploaded.</p>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      {rfps.map((r) => (
                        <button
                          key={r.filename}
                          onClick={() => toggle(rfpSel, setRfpSel, r.filename)}
                          className={`rounded-full px-2.5 py-1 text-xs transition ${
                            rfpSel.includes(r.filename)
                              ? "bg-navy text-white"
                              : "bg-slate-50 text-slate-600 hover:bg-slate-100"
                          }`}
                        >
                          {r.filename}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </Card>

          {error && (
            <Banner tone="rose" className="mt-5">
              {error}
            </Banner>
          )}

          {/* Suggested questions — shown on an empty chat */}
          {messages.length === 0 && (
            <div className="mt-5">
              <div className="mb-2 text-xs font-medium text-slate-500">Suggested questions</div>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => ask(s)}
                    disabled={busy}
                    className="rounded-full border border-slate-200 px-3 py-1.5 text-sm text-slate-600 transition hover:border-navy hover:bg-navy-tint hover:text-navy disabled:opacity-50"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Conversation */}
          <div className="mt-5 space-y-6">
            {messages.map((m, i) =>
              m.role === "user" ? (
                <div key={i} className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl bg-navy px-4 py-2.5 text-sm text-white">
                    {m.content}
                  </div>
                </div>
              ) : (
                <AssistantMessage
                  key={i}
                  msg={m}
                  evaluating={!!evaluating[i]}
                  onEvaluate={() => evaluateMessage(i)}
                />
              )
            )}
            {busy && (
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <Loader2 className="h-4 w-4 animate-spin" /> Thinking…
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
