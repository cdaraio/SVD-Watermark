import { useState, useCallback } from "react";
import { Zap, Download, AlertCircle, Settings2 } from "lucide-react";
import DropZone from "../components/ui/DropZone.jsx";
import Spinner, { SkeletonBlock } from "../components/ui/Spinner.jsx";
import { applicaAttacco } from "../api/client.js";

const CONFIG_ATTACCHI = {
  jpeg: {
    nome: "Compressione JPEG",
    descrizione: "Riduce la qualità dell'immagine simulando il salvataggio in formato JPEG.",
    param: "quality", 
    min: 1, max: 100, step: 1, def: 50,
    unita: "qualità",
    suggerimento: (v) => v <= 30 ? "Aggressivo" : v <= 60 ? "Moderato" : "Leggero",
  },
  gaussian: {
    nome: "Rumore Gaussiano",
    descrizione: "Aggiunge un disturbo visivo casuale su tutta l'immagine.",
    param: "sigma", 
    min: 1, max: 100, step: 1, def: 25,
    unita: "σ",
    suggerimento: (v) => v >= 60 ? "Pesante" : v >= 30 ? "Moderato" : "Leggero",
  },
  salt_pepper: {
    nome: "Salt Pepper",
    descrizione: "Sparge pixel completamente bianchi e neri a caso nell'immagine.",
    param: "density", 
    min: 0.01, max: 0.5, step: 0.01, def: 0.05,
    unita: "densità",
    suggerimento: (v) => v >= 0.3 ? "Pesante" : v >= 0.1 ? "Moderato" : "Leggero",
  },
  cropping: {
    nome: "Ritaglio (Cropping)",
    descrizione: "Rimuove una porzione dell'immagine riempiendola di nero.",
    param: "crop_fraction",
    min: 0.01, max: 0.5, step: 0.01, def: 0.1,
    unita: "frazione",
    suggerimento: (v) => v >= 0.35 ? "Pesante" : v >= 0.15 ? "Moderato" : "Leggero",
  },
  rotation: {
    nome: "Rotazione",
    descrizione: "Ruota l'immagine per testare la resistenza ai cambiamenti geometrici.",
    param: "angle", 
    min: 1, max: 45, step: 1, def: 10,
    unita: "°",
    suggerimento: (v) => v >= 30 ? "Ampia" : v >= 15 ? "Media" : "Lieve",
  },
};

function scaricaImmagineBase64(b64, nomeFile) {
  const link = document.createElement("a");
  link.href = `data:image/png;base64,${b64}`;
  link.download = nomeFile;
  link.click();
}

export default function VistaAttacco() {
  const [fileImmagine, setFileImmagine] = useState(null);
  const [tipoAttacco, setTipoAttacco] = useState("jpeg");
  const [valoreParametro, setValoreParametro] = useState(CONFIG_ATTACCHI.jpeg.def);
  const [caricamento, setCaricamento] = useState(false);
  const [errore, setErrore] = useState(null);
  const [risultato, setRisultato] = useState(null);

  const configAttacco = CONFIG_ATTACCHI[tipoAttacco];

  // Aggiorna i valori di default quando si cambia l'attacco dal menu a tendina
  const cambiaTipoAttacco = useCallback((e) => {
    const nuovoTipo = e.target.value;
    setTipoAttacco(nuovoTipo);
    setValoreParametro(CONFIG_ATTACCHI[nuovoTipo].def);
    setRisultato(null);
    setErrore(null);
  }, []);

  const eseguiAttacco = async () => {
    if (!fileImmagine) return;
    setCaricamento(true);
    setErrore(null);
    setRisultato(null);
    
    try {

      const dati = await applicaAttacco({
        imageFile: fileImmagine,
        attackType: tipoAttacco,
        params: { [configAttacco.param]: valoreParametro },
      });
      setRisultato(dati);
    } catch (err) {
      setErrore(err.message);
    } finally {
      setCaricamento(false);
    }
  };

  const bottoneAttivo = fileImmagine && !caricamento;

  return (
    <div className="max-w-5xl mx-auto px-8 py-10 animate-fade-in">
      
      {/* Intestazione */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-cyber/10 border border-cyber/25 flex items-center justify-center">
            <Zap className="w-4 h-4 text-cyber" />
          </div>
          <h1 className="text-xl font-semibold text-zinc-100">Simulazione Attacchi</h1>
        </div>
        <p className="text-sm text-zinc-500 ml-11">
          Applica alterazioni all'immagine per testare la resistenza del watermark.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Zona di caricamento */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider px-1">
            Immagine di Input
          </label>
          <DropZone
            onFile={(f) => { setFileImmagine(f); setRisultato(null); }}
            label="Trascina l'immagine con watermark qui"
            sublabel="Supporta PNG, JPEG, BMP"
          />
        </div>

        {/* Pannello di configurazione dell'attacco */}
        <div className="flex flex-col gap-3">
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider px-1">
            Impostazioni Attacco
          </label>

          <div className="flex-1 p-5 rounded-xl bg-panel border border-panel-border flex flex-col gap-5">
            
            <div className="flex flex-col gap-2">
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">
                Tipo di Attacco
              </p>
              <div className="relative">
                <select
                  value={tipoAttacco}
                  onChange={cambiaTipoAttacco}
                  className="w-full appearance-none bg-[#111] text-gray-100 text-sm font-medium
                    rounded-lg px-3 py-2.5 pr-9 border border-panel-border
                    focus:outline-none focus:ring-2 focus:ring-cyber/40 focus:border-cyber
                    cursor-pointer"
                >
                  {Object.entries(CONFIG_ATTACCHI).map(([chiave, config]) => (
                    <option key={chiave} value={chiave}>
                      {config.nome}
                    </option>
                  ))}
                </select>
                <Settings2 className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 pointer-events-none" />
              </div>
              <p className="text-xs text-zinc-600">{configAttacco.descrizione}</p>
            </div>

            {/* Slider per il parametro */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">
                  {configAttacco.unita === "°" ? "Angolo" : configAttacco.unita.charAt(0).toUpperCase() + configAttacco.unita.slice(1)}
                </p>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-zinc-500">{configAttacco.suggerimento(valoreParametro)}</span>
                  <span className="text-sm font-bold tabular-nums text-cyber bg-cyber/10 border border-cyber/20 px-2.5 py-0.5 rounded-lg">
                    {configAttacco.step >= 1 ? valoreParametro : valoreParametro.toFixed(2)}{configAttacco.unita === "°" ? "°" : ""}
                  </span>
                </div>
              </div>
              <input
                type="range"
                min={configAttacco.min}
                max={configAttacco.max}
                step={configAttacco.step}
                value={valoreParametro}
                onChange={(e) => setValoreParametro(parseFloat(e.target.value))}
                className="w-full h-1.5 appearance-none rounded-full cursor-pointer
                  bg-zinc-800
                  [&::-webkit-slider-thumb]:appearance-none
                  [&::-webkit-slider-thumb]:w-4
                  [&::-webkit-slider-thumb]:h-4
                  [&::-webkit-slider-thumb]:rounded-full
                  [&::-webkit-slider-thumb]:bg-cyber
                  [&::-webkit-slider-thumb]:cursor-pointer
                  [&::-webkit-slider-thumb]:shadow-lg"
              />
              <div className="flex justify-between text-[10px] text-zinc-600">
                <span>{configAttacco.min}{configAttacco.unita === "°" ? "°" : ""}</span>
                <span>{configAttacco.max}{configAttacco.unita === "°" ? "°" : ""}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottone esecuzione */}
      <button
        disabled={!bottoneAttivo}
        onClick={eseguiAttacco}
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
            Applicazione {configAttacco.nome}...
          </>
        ) : (
          <>
            <Zap className="w-4 h-4" />
            Applica Attacco
          </>
        )}
      </button>

      {/* Gestione errori */}
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
          <SkeletonBlock className="h-72 rounded-xl" />
        </div>
      )}

      {/* Mostra il risultato */}
      {risultato && !caricamento && (
        <div className="mt-8 animate-fade-in">
          <div className="h-px bg-zinc-800 mb-8" />

          <div className="rounded-xl bg-panel border border-panel-border overflow-hidden">
            <div className="px-5 py-3.5 border-b border-panel-border flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-cyber uppercase tracking-wider">
                  Immagine Attaccata
                </span>
                <span className="text-[10px] text-zinc-600">
                  — {CONFIG_ATTACCHI[risultato.attack_type]?.nome ?? risultato.attack_type}
                </span>
              </div>
              <button
                onClick={() => scaricaImmagineBase64(risultato.attacked_image, `immagine_attaccata_${risultato.attack_type}.png`)}
                className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-cyber py-1.5 px-3 rounded-lg bg-[#111] hover:bg-[#1a1a1a] transition-colors border border-panel-border"
              >
                <Download className="w-3.5 h-3.5" />
                Scarica
              </button>
            </div>
              <div className="flex items-center justify-center p-6 bg-[#050505] min-h-[260px]">
              <img
                src={`data:image/png;base64,${risultato.attacked_image}`}
                alt="Immagine attaccata"
                className="max-h-72 max-w-full object-contain rounded-lg"
              />
            </div>
          </div>

          <p className="mt-3 text-xs text-zinc-600 text-center">
            Usa questa immagine come input nel prossimo step di Estrazione del Watermark.
          </p>
        </div>
      )}
    </div>
  );
}