import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Renders markdown (bold, headings, lists, tables) from LLM answers. Styled with
// the Tailwind typography plugin; `prose-sm` keeps it sized for answer cards.
export function Markdown({ children, className = "" }) {
  return (
    <div className={`prose prose-sm max-w-none prose-slate prose-headings:font-semibold prose-pre:bg-slate-50 ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}

export function Card({ className = "", children }) {
  return (
    <div className={`rounded-2xl border border-slate-200 bg-white ${className}`}>
      {children}
    </div>
  );
}

const PILL = {
  navy: "bg-navy-tint text-navy",
  blue: "bg-sky-50 text-sky-700",
  indigo: "bg-indigo-50 text-indigo-700",
  amber: "bg-amber-50 text-amber-700",
  green: "bg-emerald-50 text-emerald-700",
  rose: "bg-rose-50 text-rose-700",
  slate: "bg-slate-50 text-slate-500 border border-slate-200",
};

export function Pill({ color = "slate", className = "", children }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${PILL[color] || PILL.slate} ${className}`}
    >
      {children}
    </span>
  );
}

const TILE = {
  navy: "bg-navy-tint text-navy",
  blue: "bg-sky-50 text-sky-600",
  indigo: "bg-indigo-50 text-indigo-600",
  amber: "bg-amber-50 text-amber-600",
  green: "bg-emerald-50 text-emerald-600",
  rose: "bg-rose-50 text-rose-600",
};

export function IconTile({ color = "navy", className = "", children }) {
  return (
    <div
      className={`flex h-9 w-9 items-center justify-center rounded-lg ${TILE[color] || TILE.navy} ${className}`}
    >
      {children}
    </div>
  );
}

export function PageHeader({ title, subtitle, action }) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

const BTN = {
  primary: "bg-navy text-white hover:bg-navy-deep",
  secondary: "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
  ghost: "text-navy hover:bg-navy-tint",
};

export function Button({ variant = "primary", className = "", ...props }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${BTN[variant]} ${className}`}
      {...props}
    />
  );
}

const BANNER = {
  amber: "bg-amber-50 text-amber-800 border-amber-200",
  blue: "bg-sky-50 text-sky-800 border-sky-200",
  rose: "bg-rose-50 text-rose-800 border-rose-200",
};

export function Banner({ tone = "amber", className = "", children }) {
  return (
    <div className={`rounded-xl border px-4 py-2.5 text-sm ${BANNER[tone]} ${className}`}>
      {children}
    </div>
  );
}

export function SectionTitle({ icon: Icon, children, right }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <span className="flex items-center gap-2 text-sm font-medium text-slate-700">
        {Icon && <Icon className="h-4 w-4 text-slate-500" />}
        {children}
      </span>
      {right}
    </div>
  );
}
