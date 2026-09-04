import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar.jsx";

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-white text-slate-900">
      <Sidebar />
      <main className="flex-1 overflow-x-hidden px-8 py-7">
        <div className="mx-auto max-w-7xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
