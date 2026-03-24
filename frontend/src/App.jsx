import { useState } from "react";
import Sidebar from "./components/Layout/Sidebar.jsx";
import VistaWatermark from "./views/VistaWatermark.jsx";
import VistaAttacco from "./views/VistaAttacco.jsx";
import VistaEstrazione from "./views/VistaEstrazione.jsx";

const VIEWS = {
  embed: VistaWatermark,
  attack: VistaAttacco,
  extract: VistaEstrazione,
};

export default function App() {
  const [activeView, setActiveView] = useState("embed");
  const ActiveComponent = VIEWS[activeView];

  return (
    <div className="flex h-screen bg-[#050505] text-gray-200 overflow-hidden">
      <Sidebar activeView={activeView} onNavigate={setActiveView} />
      <main className="flex-1 overflow-y-auto bg-[#050505]">
        <ActiveComponent />
      </main>
    </div>
  );
}
