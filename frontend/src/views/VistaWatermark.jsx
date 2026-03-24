import { useState, useCallback } from "react";
import { ShieldCheck, Download, Copy, Check, AlertCircle } from "lucide-react";
import DropZone from "../components/ui/DropZone.jsx";
import MetricCard from "../components/ui/MetricCard.jsx";
import Spinner, { SkeletonBlock } from "../components/ui/Spinner.jsx";
import { inserisciWatermark } from "../api/client.js";
 
function valutaPSNR(psnr) {
  if (psnr === Infinity || psnr > 40) return "good";
  if (psnr >= 30) return "warn";
  return "bad";
} 

function valutaSSIM(ssim) {
  if (ssim >= 0.95) return "good";
  if (ssim >= 0.80) return "warn";
  return "bad";
}
 
function scaricaImmagineBase64(b64, nomeFile) {
  const link = document.createElement("a");
  link.href = `data:image/png;base64,${b64}`;
  link.download = nomeFile;
  link.click();
}

export default function VistaWatermark() {
  const [imgOriginale, setImgOriginale] = useState(null);
  const [fileWatermark, setFileWatermark] = useState(null);
  const [forzaAlpha, setForzaAlpha] = useState(0.1);
  const [caricamento, setCaricamento] = useState(false);
  const [errore, setErrore] = useState(null);
  const [risultato, setRisultato] = useState(null); 
  const [copiato, setCopiato] = useState(false);
  const [anteprimaOriginale, setAnteprimaOriginale] = useState(null);

  // Gestisce il caricamento dell'immagine principale e crea l'anteprima
  const gestisciImgOriginale = useCallback((file) => {
    setImgOriginale(file);
    if (file) setAnteprimaOriginale(URL.createObjectURL(file));
    else setAnteprimaOriginale(null);
  }, []);

  const applicaWatermark = async () => {
    if (!imgOriginale || !fileWatermark) return;
    setCaricamento(true);
    setErrore(null);
    setRisultato(null);
    
    try {
      const dati = await inserisciWatermark({ 
        hostFile: imgOriginale, 
        watermarkFile: fileWatermark, 
        alpha: forzaAlpha 
      });
      setRisultato(dati);
    } catch (err) {
      setErrore(err.message);
    } finally {
      setCaricamento(false);
    }
  };

  const copiaChiave = async () => {
    if (!risultato?.key) return;
    await navigator.clipboard.writeText(risultato.key);
    setCopiato(true);
    setTimeout(() => setCopiato(false), 2000); // resetta il check dopo 2 secondi
  };
 
  const bottoneAttivo = imgOriginale && fileWatermark && !caricamento;

  return (
    <div className="max-w-5xl mx-auto px-8 py-10 animate-fade-in">
      
      {/* Intestazione */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-cyber/10 border border-cyber/25 flex items-center justify-center">
            <ShieldCheck className="w-4 h-4 text-cyber" />
          </div>
          <h1 className="text-xl font-semibold text-zinc-100">Inserimento Watermark</h1>
        </div>
        <p className="text-sm text-zinc-500 ml-11">
          Inserisce un watermark invisibile modificando i valori singolari (SVD) a blocchi 8x8.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* Zona drop per l'immagine da proteggere */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider px-1">
            Immagine Originale
          </label>
          <DropZone
            onFile={gestisciImgOriginale}
            label="Trascina l'immagine qui"
          />
        </div>
        
        {/* Zona drop per il logo/watermark */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider px-1">
            Watermark  
          </label>
          <DropZone
            onFile={setFileWatermark}
            label="Trascina il watermark qui"
          />
        </div>
      </div>

      {/* Slider per il valore Alpha */}
      <div className="p-5 rounded-xl bg-panel border border-panel-border mb-6">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-sm font-medium text-zinc-200">Forza di Inserimento (α)</p>
            <p className="text-xs text-zinc-500 mt-0.5">
              Un valore alto aumenta la resistenza ma riduce la qualità visiva dell'immagine.
            </p>
          </div>
          <span className="text-lg font-bold tabular-nums text-cyber bg-cyber/10 border border-cyber/20 px-3 py-1 rounded-lg">
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
            bg-zinc-800
            [&::-webkit-slider-thumb]:appearance-none
            [&::-webkit-slider-thumb]:w-4
            [&::-webkit-slider-thumb]:h-4
            [&::-webkit-slider-thumb]:rounded-full
            [&::-webkit-slider-thumb]:bg-cyber
            [&::-webkit-slider-thumb]:cursor-pointer
            [&::-webkit-slider-thumb]:shadow-lg"
        />
        <div className="flex justify-between mt-1.5 text-[10px] text-zinc-600">
          <span>0.01 — Leggero</span>
          <span>0.50 — Forte</span>
        </div>
      </div>

      {/* Bottone d'azione */}
      <button
        disabled={!bottoneAttivo}
        onClick={applicaWatermark}
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
            Elaborazione SVD in corso...
          </>
        ) : (
          <>
            <ShieldCheck className="w-4 h-4" />
            Applica Watermark
          </>
        )}
      </button>

      {/* Box di errore */}
      {errore && (
        <div className="mt-4 flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 animate-fade-in">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <p className="text-sm">{errore}</p>
        </div>
      )}

      {/* Effetto scheletro durante il caricamento */}
      {caricamento && (
        <div className="mt-8 animate-fade-in">
          <div className="h-px bg-panel-border mb-8" />
          <div className="grid grid-cols-2 gap-4 mb-4">
            <SkeletonBlock className="h-64 rounded-xl" />
            <SkeletonBlock className="h-64 rounded-xl" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <SkeletonBlock className="h-28 rounded-xl" />
            <SkeletonBlock className="h-28 rounded-xl" />
          </div>
        </div>
      )}

      {/* Schermata dei risultati */}
      {risultato && !caricamento && (
        <div className="mt-8 animate-fade-in">
          <div className="h-px bg-panel-border mb-8" />

          {/* Confronto immagini */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            
            <div className="rounded-xl bg-panel border border-panel-border overflow-hidden">
              <div className="px-4 py-3 border-b border-panel-border flex items-center justify-between">
                <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                  Originale
                </span>
                <span className="text-[10px] text-zinc-600">Immagine di partenza</span>
              </div>
              <div className="flex items-center justify-center p-4 bg-[#050505] min-h-[200px]">
                {anteprimaOriginale ? (
                  <img
                    src={anteprimaOriginale}
                    alt="Originale"
                    className="max-h-56 max-w-full object-contain rounded-lg"
                  />
                ) : (
                  <span className="text-xs text-zinc-600">Nessuna anteprima</span>
                )}
              </div>
            </div>

            <div className="rounded-xl bg-panel border border-panel-border overflow-hidden">
              <div className="px-4 py-3 border-b border-panel-border flex items-center justify-between">
                <span className="text-xs font-semibold text-cyber uppercase tracking-wider">
                  Watermarked
                </span>
                <span className="text-[10px] text-zinc-600">Risultato con watermark</span>
              </div>
              <div className="flex items-center justify-center p-4 bg-[#050505] min-h-[200px]">
                <img
                  src={`data:image/png;base64,${risultato.watermarked_image}`}
                  alt="Watermarked"
                  className="max-h-56 max-w-full object-contain rounded-lg"
                />
              </div>
            </div>
          </div>

          {/* Card delle metriche */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <MetricCard
              label="PSNR"
              value={risultato.psnr === null ? "∞" : risultato.psnr}
              unit="dB"
              description="Peak Signal-to-Noise Ratio. Sopra 40 dB = distorsione invisibile all'occhio umano."
              status={valutaPSNR(risultato.psnr)}
            />
            <MetricCard
              label="SSIM"
              value={risultato.ssim}
              description="Indice di somiglianza strutturale. Più vicino a 1 = qualità migliore."
              status={valutaSSIM(risultato.ssim)}
            />
          </div>

          {/* Bottoni download e copia */}
          <div className="grid grid-cols-2 gap-3 mt-4">
            <button
              onClick={() => scaricaImmagineBase64(risultato.watermarked_image, "immagine_watermaked.png")}
              className="flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-[#111] hover:bg-[#1a1a1a] text-zinc-300 text-sm font-medium transition-colors border border-panel-border hover:border-cyber/30"
            >
              <Download className="w-4 h-4" />
              Scarica Immagine
            </button>
            <button
              onClick={copiaChiave}
              className="flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-[#111] hover:bg-[#1a1a1a] text-zinc-300 text-sm font-medium transition-colors border border-panel-border hover:border-cyber/30"
            >
              {copiato ? (
                <>  
                  <Check className="w-4 h-4 text-cyber" />
                  <span className="text-cyber">Chiave Copiata!</span>
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  Copia Chiave Segreta
                </>
              )}
            </button>
          </div>

          <p className="mt-3 text-xs text-zinc-600 text-center">
            La chiave segreta contiene i valori singolari SVD originali. Ti servirà per poter estrarre il watermark in seguito.
          </p>
        </div>
      )}
    </div>
  );
}