import { ShieldCheck, Zap, Search, GraduationCap } from "lucide-react";

const MENU_ITEMS = [
  {
    id: "embed", 
    titolo: "Inserimento Watermark",
    descrizione: "Watermarking SVD",
    Icona: ShieldCheck,
  },
  {
    id: "attack",
    titolo: "Simulazione Attacchi",
    descrizione: "Test di robustezza del watermark",
    Icona: Zap,
  },
  {
    id: "extract",
    titolo: "Estrazione Watermark",
    descrizione: "Recupero semi-blind",
    Icona: Search,
  },
];

// Barra laterale di navigazione
export default function Sidebar({ activeView, onNavigate }) {
  return (
    <aside className="flex flex-col w-72 shrink-0 h-full bg-[#050505] border-r border-panel-border">
      
      {/* Logo e Titolo del progetto */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-panel-border">
        <div className="w-8 h-8 rounded-lg bg-cyber flex items-center justify-center shrink-0">
          <ShieldCheck className="w-4 h-4 text-black" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-zinc-100 truncate">
            WatermarkSVD
          </p>
          <p className="text-[11px] text-zinc-500 truncate">Watermarking Tool</p>
        </div>
      </div>

      {/* Menu di Navigazione */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        <p className="px-2 mb-3 text-[10px] font-semibold text-zinc-600 uppercase tracking-widest" style={{letterSpacing:'0.18em'}}>
          Pipeline
        </p>
        
        {MENU_ITEMS.map(({ id, titolo, descrizione, Icona }) => {
          const selezionato = id === activeView;
          
          return (
            <button
              key={id}
              onClick={() => onNavigate(id)}
              className={[
                "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all duration-150 group",
                selezionato
                  ? "bg-cyber/10 border border-cyber/25 text-cyber"
                  : "text-zinc-400 hover:text-gray-100 hover:bg-[#111] border border-transparent",
              ].join(" ")}
            >
              <div
                className={[
                  "w-7 h-7 rounded-md flex items-center justify-center shrink-0 transition-colors",
                  selezionato
                    ? "bg-cyber/15 text-cyber"
                    : "bg-[#111] text-zinc-500 group-hover:text-zinc-300",
                ].join(" ")}
              >
                <Icona className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0">
                <p
                  className={`text-sm font-medium truncate ${
                    selezionato ? "text-cyber" : "text-zinc-300"
                  }`}
                >
                  {titolo}
                </p>
                <p className="text-[11px] text-zinc-600 truncate">{descrizione}</p>
              </div>
              
              {/* Punto pagina attiva */}
              {selezionato && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-cyber shrink-0 shadow-cyber-sm" />
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer*/}
      <div className="px-5 py-4 border-t border-panel-border">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-full bg-zinc-800 flex items-center justify-center">
            <GraduationCap className="w-3.5 h-3.5 text-zinc-400" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium text-zinc-400 truncate">Progetto SMM</p>
            <p className="text-[11px] text-zinc-600 truncate">SVD Watermarking</p>
          </div>
        </div>
      </div>
      
    </aside>
  );
}