import { useNavigate } from "react-router-dom";
import {
  Search,
  MessageCircle,
  CheckCircle2,
  ArrowRight,
} from "lucide-react";
import { Card, IconTile, Button, SectionTitle } from "../components/ui.jsx";

const STATS = [
  ["RAG", "Retrieval engine"],
  ["Cited", "Every answer sourced"],
  ["Multi-format", "PDF · DOCX · PPTX · TXT"],
  ["Bid", "Decision support"],
];

const FEATURES = [
  {
    icon: Search,
    color: "blue",
    title: "RFP Analysis",
    body: "Reads and understands incoming RFP documents. Extracts requirements, deadlines, and evaluation criteria automatically.",
  },
  {
    icon: MessageCircle,
    color: "indigo",
    title: "Grounded Q&A",
    body: "Answers any question about your RFP using your company documents. Every answer includes a source citation.",
  },
  {
    icon: CheckCircle2,
    color: "green",
    title: "Bid / No-Bid",
    body: "Evaluates whether your company meets the RFP requirements and recommends whether to pursue the tender.",
  },
];

const TECH = [
  ["Python", "Language"],
  ["LangChain", "RAG pipeline"],
  ["ChromaDB", "Vector store"],
  ["Multi-provider LLM", "Groq · OpenAI · Anthropic · Gemini · Local"],
  ["MiniLM", "Embeddings"],
  ["Cross-encoder", "Reranker"],
  ["FastAPI", "API layer"],
  ["LLM Judge", "Evaluation"],
  ["React (Vite)", "Frontend"],
];

const STEPS = [
  {
    to: "/knowledge-base",
    target: "Knowledge base",
    desc: "Upload your company documents — CVs, certificates, past projects, capability statements.",
  },
  {
    to: "/analyze",
    target: "Analyze RFP",
    desc: "Upload the RFP you want to analyze — PDF, DOCX, PPTX, or TXT.",
  },
  {
    to: "/ask",
    target: "Ask Questions",
    desc: "Ask anything about the RFP, with cited answers grounded in your documents.",
  },
    {
    to: "/workspace",
    target: "Bids workspace",
    desc: "Manage saved RFPs and bids.",
  },
];

export default function About() {
  const navigate = useNavigate();

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-navy to-navy-deep px-8 py-10 text-white">
        <div className="absolute right-8 top-8 hidden rounded-xl bg-white p-2 shadow-sm sm:block">
          <img src="/download.png" alt="SanadAI" className="h-14 w-14 object-contain" />
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-gold/40 bg-white/5 px-3 py-1 text-xs font-medium uppercase tracking-wide text-gold">
          AI-Powered RFP Intelligence
        </span>
        <h1 className="mt-4 text-3xl font-bold tracking-tight">
          Welcome to <span className="text-gold">SanadAI</span>
        </h1>
        <p className="mt-3 max-w-2xl leading-relaxed text-white/70">
          A retrieval-augmented system that helps your team respond to RFPs faster and more
          accurately. Upload your company documents and incoming RFPs, then ask questions and get
          grounded answers with full source citations.
        </p>
        <div className="mt-8 flex flex-wrap gap-8">
          {STATS.map(([n, l]) => (
            <div key={n} className="border-l-2 border-gold pl-3">
              <div className="text-base font-semibold">{n}</div>
              <div className="mt-0.5 text-xs text-white/50">{l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* What SanadAI does */}
      <div>
        <SectionTitle>What SanadAI does</SectionTitle>
        <div className="grid gap-4 sm:grid-cols-3">
          {FEATURES.map(({ icon: Icon, color, title, body }) => (
            <Card key={title} className="p-5">
              <IconTile color={color} className="mb-3">
                <Icon className="h-[18px] w-[18px]" />
              </IconTile>
              <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-500">{body}</p>
            </Card>
          ))}
        </div>
      </div>

      {/* Tech stack */}
      <div>
        <SectionTitle>Tech stack</SectionTitle>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {TECH.map(([n, r]) => (
            <Card key={n} className="p-4 text-center">
              <div className="text-sm font-semibold text-slate-800">{n}</div>
              <div className="mt-1 text-xs text-slate-400">{r}</div>
            </Card>
          ))}
        </div>
      </div>

      {/* Where to start */}
      <div>
        <SectionTitle>Where to start</SectionTitle>
        <div className="space-y-2">
          {STEPS.map((step, i) => (
            <button
              key={i}
              onClick={() => navigate(step.to)}
              className="flex w-full items-start gap-4 rounded-xl border border-slate-200 bg-white px-4 py-3.5 text-left transition hover:border-navy hover:bg-navy-tint"
            >
              <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-navy text-xs font-bold text-gold">
                {i + 1}
              </span>
              <div className="flex-1">
                <div className="text-sm font-semibold text-slate-900">
                  Go to {step.target}
                </div>
                <div className="mt-0.5 text-xs text-slate-500">{step.desc}</div>
              </div>
              <ArrowRight className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-300" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
