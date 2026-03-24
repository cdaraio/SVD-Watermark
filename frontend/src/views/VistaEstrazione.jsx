import { useState } from "react";
import { Search, Download, AlertCircle, KeyRound, Info } from "lucide-react";
import DropZone from "../components/ui/DropZone.jsx";
import CircularGauge from "../components/ui/CircularGauge.jsx";
import Spinner, { SkeletonBlock } from "../components/ui/Spinner.jsx";
import { estraiWatermark } from "../api/client.js";

// Funzione per scaricare l'immagine decodificata
function scaricaImmagineBase64(b64, nomeFile) {
  const link = document.createElement("a");
  link.href = `data:image/png;base64,${b64}`;
  link.download = nomeFile;
  link.click();
}

// Valuta il risultato della Correlazione Normalizzata (NC)
function valutaNC(nc) {
  if (nc >= 0.9)  return { text: "Ottimo", colore: "text-emerald-400" };
  if (nc >= 0.7)  return { text: "Accettabile", colore: "text-amber-400"  };
  return          { text: "Scarso", colore: "text-red-400"    };
}

// Valuta il Tasso di Errore (BER), più è basso meglio è
function valutaBER(ber) {
  if (ber <= 0.05) return { text: "Ottimo", colore: "text-emerald-400" };
  if (ber <= 0.15) return { text: "Accettabile", colore: "text-amber-400"  };
  return           { text: "Scarso", colore: "text-red-400"    };
}

export default function VistaEstrazione() {
  // Stati del componente
  const [watermark, setWatermark] = useState(null); 
  const [watermarkOriginale, setWatermarkOriginale] = useState(null); 
  const [chiaveSegreta, setChiaveSegreta] = useState("");
  const [forzaAlpha, setForzaAlpha] = useState(0.1);
  const [caricamento, setCaricamento] = useState(false);
  const [errore, setErrore] = useState(null);
  const [risultato, setRisultato] = useState(null); 

  // Gestisce la chiamata al backend per l'estrazione
  const eseguiEstrazione = async () => {
    if (!watermark || !watermarkOriginale || !chiaveSegreta.trim()) return;
    setCaricamento(true);
    setErrore(null);
    setRisultato(null);
    try {
      const dati = await estraiWatermark({
        watermarkedFile: watermark,
        originalWatermarkFile: watermarkOriginale,
        key: chiaveSegreta.trim(),
        alpha: forzaAlpha,
      });
      setRisultato(dati);
    } catch (err) {
      setErrore(err.message);
    } finally {
      setCaricamento(false);
    }
  };

  // Controlla se abbiamo tutti i dati necessari per sbloccare il bottone
  const bottoneAttivo = watermark && watermarkOriginale && chiaveSegreta.trim() && !caricamento;
  const statoNC = risultato ? valutaNC(risultato.nc) : null;
  const statoBER = risultato ? valutaBER(risultato.ber) : null;

  return (
    <div className="max-w-5xl mx-auto px-8 py-10 animate-fade-in">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-cyber/10 border border-cyber/25 flex items-center justify-center">
            <Search className="w-4 h-4 text-cyber" />
          </div>
          <h1 className="text-xl font-semibold text-zinc-100">Estrazione Watermark</h1>
        </div>
        <p className="text-sm text-zinc-500 ml-11">
          Recupero del watermark utilizzando la chiave generata nella fase di inserimento.
        </p>
      </div>

      {/* Area di caricamento file */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="flex flex-col gap-2">
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider px-1">
            Immagine con watermark / Immagine attaccata
          </label>
          <DropZone
            onFile={(file) => { setWatermark(file); setRisultato(null); }}
            label="Trascina qui l'immagine attaccata"
            sublabel="Il risultato della fase di simulazione attacco"
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider px-1">
            Watermark Originale
          </label>
          <DropZone
            onFile={(file) => { setWatermarkOriginale(file); setRisultato(null); }}
            label="Trascina qui il watermark originale"
            sublabel="Serve solo per calcolare le metriche NC e BER"
          />
        </div>
      </div>

      {/* Sezione Chiave Segreta e Valore Alpha */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        
        <div className="col-span-3 flex flex-col gap-2">
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider px-1 flex items-center gap-1.5">
            <KeyRound className="w-3 h-3 text-cyber" />
            Chiave Segreta
          </label>
          <div className="relative flex-1">
            <textarea
              value={chiaveSegreta}
              onChange={(e) => setChiaveSegreta(e.target.value)}
              placeholder="Incolla qui la chiave in base64 ottenuta durante l'inserimento..."
              rows={4}
              className="w-full h-full resize-none rounded-xl bg-panel border border-panel-border
                text-zinc-300 text-xs font-mono placeholder-zinc-700
                px-4 py-3 focus:outline-none focus:ring-2 focus:ring-cyber/40 focus:border-cyber
                transition-all"
            />
            {chiaveSegreta.length > 0 && (
              <div className="absolute bottom-2.5 right-3 text-[10px] text-zinc-600">
                {chiaveSegreta.length} caratteri
              </div>
            )}
          </div>
        </div>

        <div className="col-span-2 flex flex-col gap-2">
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider px-1">
            Forza di inserimento (α)
          </label>
          <div className="flex-1 p-4 rounded-xl bg-panel border border-panel-border flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <p className="text-xs text-zinc-500">Deve coincidere con l'originale</p>
              <span className="text-sm font-bold tabular-nums text-cyber bg-cyber/10 border border-cyber/20 px-2.5 py-0.5 rounded-lg">
                {forzaAlpha.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min={0.01}
              max={0.5}
              step={0.01}
              value={forzaAlpha}
              onChange={(e) => setForzaAlpha(parseFloat(e.target.value))}
              className="w-full h-1.5 appearance-none rounded-full cursor-pointer
                bg-zinc-700
                [&::-webkit-slider-thumb]:appearance-none
                [&::-webkit-slider-thumb]:w-4
                [&::-webkit-slider-thumb]:h-4
                [&::-webkit-slider-thumb]:rounded-full
                  [&::-webkit-slider-thumb]:bg-cyber
                [&::-webkit-slider-thumb]:cursor-pointer
                [&::-webkit-slider-thumb]:shadow-lg"
            />
            <div className="flex items-start gap-2 p-3 rounded-lg bg-[#111]">
              <Info className="w-3.5 h-3.5 text-cyber/50 mt-0.5 shrink-0" />
              <p className="text-[11px] text-zinc-600 leading-relaxed">
                Imposta lo stesso valore α usato all'inizio. Se è sbagliato, il watermark estratto sarà corrotto.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Bottone di invio */}
      <button
        disabled={!bottoneAttivo}
        onClick={eseguiEstrazione}
        className={[
          "w-full flex items-center justify-center gap-2.5 py-3 rounded-xl font-semibold text-sm transition-all duration-200",
          bottoneAttivo
            ? "bg-cyber text-black font-bold hover:shadow-cyber shadow-lg"
            : "bg-[#111] text-zinc-600 cursor-not-allowed",
        ].join(" ")}
      >
        {caricamento ? (
          <>
            <Spinner size="sm" />
            Estrazione in corso...
          </>
        ) : (
          <>
            <Search className="w-4 h-4" />
            Estrai Watermark
          </>
        )}
      </button>

      {/* Messaggio di errore */}
      {errore && (
        <div className="mt-4 flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 animate-fade-in">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <p className="text-sm">{errore}</p>
        </div>
      )}

      {/* Effetto caricamento */}
      {caricamento && (
        <div className="mt-8 animate-fade-in">
          <div className="h-px bg-panel-border mb-8" />
          <div className="grid grid-cols-3 gap-4">
            <SkeletonBlock className="col-span-2 h-64 rounded-xl" />
            <div className="flex flex-col gap-4">
              <SkeletonBlock className="h-40 rounded-xl" />
              <SkeletonBlock className="h-40 rounded-xl" />
            </div>
          </div>
        </div>
      )}

      {/* Mostra i risultati */}
      {risultato && !caricamento && (
        <div className="mt-8 animate-fade-in">
          <div className="h-px bg-panel-border mb-8" />

          <div className="grid grid-cols-3 gap-6">
            
            <div className="col-span-2 rounded-xl bg-panel border border-panel-border overflow-hidden">
              <div className="px-5 py-3.5 border-b border-panel-border flex items-center justify-between">
                <span className="text-xs font-semibold text-cyber uppercase tracking-wider">
                  Watermark Estratto
                </span>
                <button
                  onClick={() => scaricaImmagineBase64(risultato.extracted_watermark, "watermark_estratto.png")}
                  className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-cyber py-1.5 px-3 rounded-lg bg-[#111] hover:bg-[#1a1a1a] transition-colors border border-panel-border"
                >
                  <Download className="w-3.5 h-3.5" />
                  Scarica
                </button>
              </div>
              <div className="flex items-center justify-center p-6 bg-[#050505] min-h-[240px]">
                <img
                  src={`data:image/png;base64,${risultato.extracted_watermark}`}
                  alt="Watermark Estratto"
                  className="max-h-60 max-w-full object-contain rounded-lg"
                />
              </div>
            </div>

            <div className="flex flex-col gap-4">
              <p className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
                Metriche di Robustezza
              </p>

              <div className="p-5 rounded-xl bg-panel border border-panel-border flex flex-col items-center gap-1">
                <CircularGauge
                  value={risultato.nc}
                  progress={Math.max(0, risultato.nc)}
                  label="NC"
                  sublabel="Correlazione Normalizzata"
                  invertStatus={false}
                />
                <div className={`text-xs font-semibold ${statoNC.colore}`}>
                  {statoNC.text}
                </div>
                <p className="text-[11px] text-zinc-600 text-center mt-1 leading-relaxed">
                  NC ≥ 0.9 = buona estrazione
                </p>
              </div>

              <div className="p-5 rounded-xl bg-panel border border-panel-border flex flex-col items-center gap-1">
                <CircularGauge
                  value={risultato.ber}
                  progress={1 - risultato.ber}
                  label="Accuratezza Bit"
                  sublabel={`BER = ${(risultato.ber * 100).toFixed(2)}%`}
                  invertStatus={true}
                />
                <div className={`text-xs font-semibold ${statoBER.colore}`}>
                  {statoBER.text}
                </div>
                <p className="text-[11px] text-zinc-600 text-center mt-1 leading-relaxed">
                  Minore è il BER, meno bit sono corrotti
                </p>
              </div>
            </div>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-3">
            <div className={`flex items-center justify-between p-4 rounded-xl border ${
              risultato.nc >= 0.9
                ? "bg-emerald-500/5 border-emerald-500/20"
                : risultato.nc >= 0.7
                ? "bg-amber-500/5 border-amber-500/20"
                : "bg-red-500/5 border-red-500/20"
            }`}>
              <span className="text-xs text-zinc-500">Correlazione Normalizzata</span>
              <span className={`text-lg font-bold tabular-nums ${statoNC.colore}`}>
                {risultato.nc.toFixed(4)}
              </span>
            </div>
            <div className={`flex items-center justify-between p-4 rounded-xl border ${
              risultato.ber <= 0.05
                ? "bg-emerald-500/5 border-emerald-500/20"
                : risultato.ber <= 0.15
                ? "bg-amber-500/5 border-amber-500/20"
                : "bg-red-500/5 border-red-500/20"
            }`}>
              <span className="text-xs text-zinc-500">Tasso di Errore (BER)</span>
              <span className={`text-lg font-bold tabular-nums ${statoBER.colore}`}>
                {(risultato.ber * 100).toFixed(2)}%
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}