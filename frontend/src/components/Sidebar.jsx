import { NavLink } from "react-router-dom";
import {
  Home,
  Library,
  ClipboardCheck,
  PenLine,
  MessageCircle,
  Briefcase,
  Info,
  Settings2,
} from "lucide-react";

const NAV = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/knowledge-base", label: "Knowledge base", icon: Library },
  { to: "/analyze", label: "Analyze RFP", icon: ClipboardCheck },
  { to: "/draft", label: "Draft response", icon: PenLine },
  { to: "/ask", label: "Ask questions", icon: MessageCircle },
  { to: "/workspace", label: "Bids workspace", icon: Briefcase },
  { to: "/about", label: "About", icon: Info },
  { to: "/admin", label: "Admin", icon: Settings2 },
];

export default function Sidebar() {
  return (
    <aside className="flex w-60 flex-shrink-0 flex-col border-r border-slate-100 bg-white p-4">
      <div className="flex items-center gap-3 px-1 pb-2">
        <img src="/download.png" alt="SanadAI" className="h-9 w-9 rounded-xl object-contain" />
        <div>
          <div className="text-base font-semibold leading-tight">SanadAI</div>
          <div className="text-xs text-slate-400">سند · proposal co-pilot</div>
        </div>
      </div>

      <div className="px-2 pb-2 pt-4 text-xs font-medium uppercase tracking-wide text-slate-400">
        Menu
      </div>
      <nav className="flex flex-col gap-1">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                isActive
                  ? "bg-navy-tint font-medium text-navy"
                  : "text-slate-600 hover:bg-slate-50"
              }`
            }
          >
            <Icon className="h-[18px] w-[18px]" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto flex items-center gap-3 border-t border-slate-100 pt-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-navy text-xs font-medium text-white">
          SA
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">Osama Alghamdi</div>
          <div className="text-xs text-slate-400">Project Manager</div>
        </div>
      </div>
    </aside>
  );
}
