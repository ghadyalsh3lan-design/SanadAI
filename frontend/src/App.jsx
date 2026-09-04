import { useEffect, useState } from "react";
import { Routes, Route, useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { api } from "./api.js";
import Layout from "./components/Layout.jsx";
import Setup from "./pages/Setup.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import KnowledgeBase from "./pages/KnowledgeBase.jsx";
import Analyze from "./pages/Analyze.jsx";
import Draft from "./pages/Draft.jsx";
import Ask from "./pages/Ask.jsx";
import Workspace from "./pages/Workspace.jsx";
import About from "./pages/About.jsx";
import Admin from "./pages/Admin.jsx";

export default function App() {
  // On first load, check whether the knowledge base is empty. If it is (and the
  // API is reachable), route to the Setup onboarding instead of the dashboard.
  // If the API is offline, fall through to the app so the demo data still shows.
  const [status, setStatus] = useState({ loading: true, empty: false });
  const navigate = useNavigate();

  function checkKB() {
    api
      .getStats()
      .then((s) => setStatus({ loading: false, empty: s.documents === 0 }))
      .catch(() => setStatus({ loading: false, empty: false }));
  }

  // After first-run Setup completes, land on the About page (not the Dashboard).
  function handleSetupDone() {
    navigate("/about");
    checkKB();
  }

  useEffect(() => {
    checkKB();
  }, []);

  if (status.loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white text-slate-400">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  if (status.empty) {
    return <Setup onDone={handleSetupDone} />;
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/knowledge-base" element={<KnowledgeBase />} />
        <Route path="/analyze" element={<Analyze />} />
        <Route path="/draft" element={<Draft />} />
        <Route path="/ask" element={<Ask />} />
        <Route path="/workspace" element={<Workspace />} />
        <Route path="/about" element={<About />} />
        <Route path="/admin" element={<Admin />} />
      </Route>
    </Routes>
  );
}
