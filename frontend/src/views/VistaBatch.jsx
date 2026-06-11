import { useState, useRef, useCallback } from "react";
import {
  BarChart2, Play, AlertCircle, CheckCircle2,
  Download, ChevronDown, ChevronUp, Info, Loader2
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ScatterChart, Scatter, ZAxis, Cell, BarChart, Bar,
  ReferenceLine
} from "recharts";
import DropZone from "../components/ui/DropZone.jsx";

// ─── Palette ────────────────────────────────────────────────────────────────
const COLORS_IMG = [
  "#00ffe0", "#ff6b6b", "#ffd166", "#a29bfe",
  "#55efc4", "#fd79a8", "#74b9ff", "#e17055",
];

const ATTACK_LABELS = {
  no_attack: "Senza attacco",
  jpeg: "JPEG q=50",
  gaussian: "Gaussiano σ=25",
  salt_pepper: "Salt & Pepper",
  cropping: "Ritaglio 10%",
  rotation: "Rotazione 10°",
};

const ATTACK_COLORS = {
  no_attack: "#00ffe0",
  jpeg: "#ff6b6b",
  gaussian: "#ffd166",
  salt_pepper: "#a29bfe",
  cropping: "#55efc4",
  rotation: "#fd79a8",
};

// Griglia dei valori di alpha
const ALPHA_GRID = [
  0.01, 0.04, 0.07, 0.10, 0.13, 0.16, 0.19, 0.22, 0.25,
  0.28, 0.31, 0.34, 0.37, 0.40, 0.43, 0.46, 0.49
];

// ─── Util ────────────────────────────────────────────────────────────────────
function mean(arr) {
  if (!arr.length) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function statusColor(v, invert = false) {
  const good = invert ? v <= 0.05 : v >= 0.9;
  const ok = invert ? v <= 0.15 : v >= 0.7;
  if (good) return "text-emerald-400";
  if (ok) return "text-amber-400";
  return "text-red-400";
}

function Badge({ value, invert = false, decimals = 4, suffix = "" }) {
  const col = statusColor(value, invert);
  return (
    <span className={`font-bold tabular-nums ${col}`}>
      {typeof value === "number" ? value.toFixed(decimals) : value}{suffix}
    </span>
  );
}

// ─── Sezione espandibile ─────────────────────────────────────────────────────
function Section({ title, subtitle, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-xl border border-panel-border bg-panel overflow-hidden mb-6">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-white/[0.02] transition-colors"
      >
        <div>
          <p className="text-sm font-semibold text-zinc-100 text-left">{title}</p>
          {subtitle && <div className="text-xs text-zinc-500 text-left mt-0.5">{subtitle}</div>}
        </div>
        {open
          ? <ChevronUp className="w-4 h-4 text-zinc-500" />
          : <ChevronDown className="w-4 h-4 text-zinc-500" />}
      </button>
      {open && <div className="px-5 pb-5 border-t border-panel-border pt-4">{children}</div>}
    </div>
  );
}

// ─── Tooltip personalizzato ──────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#111] border border-zinc-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-zinc-400 mb-1 font-medium">α = {label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: {typeof p.value === "number" ? p.value.toFixed(4) : p.value}
        </p>
      ))}
    </div>
  );
}

// ─── Curva Alpha per singola immagine ────────────────────────────────────────
function CurvaAlpha({ risultato }) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-xs text-zinc-500 mb-2">
        Linea verticale tratteggiata = α ottimale ({risultato.best_alpha})
      </p>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={risultato.curva_alpha} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#222" />
          <XAxis
            dataKey="alpha"
            tick={{ fill: "#71717a", fontSize: 10 }}
            tickFormatter={v => v.toFixed(2)}
          />
          <YAxis tick={{ fill: "#71717a", fontSize: 10 }} domain={[0, 1.05]} />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 11, color: "#a1a1aa" }}
            formatter={v => ({
              psnr: "PSNR (norm.)",
              ssim: "SSIM",
              nc_no_attack: "NC (senza attacco)",
              nc_mean_attacks: "NC medio (tutti attacchi)",
            }[v] || v)}
          />
          <Line
            type="monotone" dataKey={d => Math.min(d.psnr / 50, 1)}
            stroke="#ffd166" name="psnr" dot={false} strokeWidth={1.5}
          />
          <Line type="monotone" dataKey="ssim" stroke="#74b9ff" name="ssim" dot={false} strokeWidth={1.5} />
          <Line type="monotone" dataKey="nc_no_attack" stroke="#00ffe0" name="nc_no_attack" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="nc_mean_attacks" stroke="#a29bfe" name="nc_mean_attacks" dot={false} strokeWidth={2} strokeDasharray="4 2" />
          <ReferenceLine x={risultato.best_alpha} stroke="#00ffe0" strokeDasharray="4 2" isFront />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Radar robustezza attacchi ───────────────────────────────────────────────
function RadarAttacchi({ matrice }) {
  const data = matrice.map(r => ({
    attack: ATTACK_LABELS[r.attack] || r.attack,
    NC: r.nc,
    "Accuratezza Bit": 1 - r.ber,
  }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <RadarChart data={data}>
        <PolarGrid stroke="#333" />
        <PolarAngleAxis dataKey="attack" tick={{ fill: "#71717a", fontSize: 9 }} />
        <PolarRadiusAxis angle={30} domain={[0, 1]} tick={{ fill: "#555", fontSize: 8 }} />
        <Radar name="NC" dataKey="NC" stroke="#00ffe0" fill="#00ffe0" fillOpacity={0.15} />
        <Radar name="Accuratezza Bit" dataKey="Accuratezza Bit" stroke="#a29bfe" fill="#a29bfe" fillOpacity={0.1} />
        <Legend wrapperStyle={{ fontSize: 11, color: "#a1a1aa" }} />
        <Tooltip
          contentStyle={{ background: "#111", border: "1px solid #333", borderRadius: 8, fontSize: 11 }}
          formatter={v => v.toFixed(4)}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}

// ─── Heatmap NC ──────────────────────────────────────────────────────────────
function HeatmapNC({ risultati }) {
  const attacchi = Object.keys(ATTACK_LABELS);
  const rows = risultati.map(r => {
    const row = { name: r.name };
    r.matrice.forEach(m => { row[m.attack] = m.nc; });
    return row;
  });

  function ncColor(v) {
    if (v >= 0.9) return "bg-emerald-500/30 text-emerald-300";
    if (v >= 0.7) return "bg-amber-500/20 text-amber-300";
    if (v >= 0.5) return "bg-orange-500/20 text-orange-300";
    return "bg-red-500/20 text-red-400";
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr>
            <th className="text-left text-zinc-500 pb-2 pr-4 font-medium">Immagine</th>
            {attacchi.map(a => (
              <th key={a} className="text-center text-zinc-500 pb-2 px-2 font-medium whitespace-nowrap">
                {ATTACK_LABELS[a]}
              </th>
            ))}
            <th className="text-center text-zinc-500 pb-2 px-2 font-medium">α ottimale</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-zinc-800/50">
              <td className="py-2 pr-4 text-zinc-300 font-medium">{row.name}</td>
              {attacchi.map(a => (
                <td key={a} className="py-1.5 px-1.5 text-center">
                  <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold tabular-nums ${ncColor(row[a] ?? 0)}`}>
                    {(row[a] ?? 0).toFixed(3)}
                  </span>
                </td>
              ))}
              <td className="py-1.5 px-2 text-center">
                <span className="inline-block px-2 py-0.5 rounded bg-cyber/10 border border-cyber/20 text-cyber text-[10px] font-bold">
                  {risultati[i].best_alpha}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Grafico α ottimale per immagine ─────────────────────────────────────────
function GraficoAlphaOttimale({ risultati }) {
  const data = risultati.map(r => ({
    name: r.name,
    alpha: r.best_alpha,
    nc_no_attack: r.matrice.find(m => m.attack === "no_attack")?.nc ?? 0,
    nc_medio: mean(r.matrice.map(m => m.nc)),
  }));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 5, right: 10, left: -15, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#222" />
        <XAxis dataKey="name" tick={{ fill: "#71717a", fontSize: 10 }} />
        <YAxis yAxisId="left" domain={[0, 0.6]} tick={{ fill: "#71717a", fontSize: 10 }} label={{ value: "α", angle: -90, position: "insideLeft", fill: "#555", fontSize: 10 }} />
        <YAxis yAxisId="right" orientation="right" domain={[0, 1]} tick={{ fill: "#71717a", fontSize: 10 }} label={{ value: "NC", angle: 90, position: "insideRight", fill: "#555", fontSize: 10 }} />
        <Tooltip
          contentStyle={{ background: "#111", border: "1px solid #333", borderRadius: 8, fontSize: 11 }}
          formatter={(v, n) => [v.toFixed(4), n]}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: "#a1a1aa" }} />
        <Bar yAxisId="left" dataKey="alpha" name="α ottimale" fill="#ffd166" opacity={0.8} radius={[3, 3, 0, 0]} />
        <Bar yAxisId="right" dataKey="nc_no_attack" name="NC (no attack)" fill="#00ffe0" opacity={0.7} radius={[3, 3, 0, 0]} />
        <Bar yAxisId="right" dataKey="nc_medio" name="NC medio" fill="#a29bfe" opacity={0.7} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── Analisi caso senza attacco ──────────────────────────────────────────────
function AnalisiNoAttack({ risultati }) {
  const rows = risultati.map(r => {
    const noAtk = r.matrice.find(m => m.attack === "no_attack") ?? {};
    const best = r.curva_alpha.find(c => c.alpha === r.best_alpha) ?? {};
    return {
      name: r.name,
      alpha: r.best_alpha,
      nc: noAtk.nc ?? 0,
      ber: noAtk.ber ?? 0,
      psnr_embed: best.psnr ?? 0,
      ssim: best.ssim ?? 0,
    };
  });

  const avgNC = mean(rows.map(r => r.nc));
  const avgBER = mean(rows.map(r => r.ber));

  return (
    <div className="flex flex-col gap-4">

      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr>
              {["Immagine", "α ottimale", "NC", "BER", "PSNR embed", "SSIM"].map(h => (
                <th key={h} className="text-left text-zinc-500 pb-2 pr-4 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-zinc-800/50">
                <td className="py-2 pr-4 text-zinc-300 font-medium">{r.name}</td>
                <td className="py-2 pr-4 text-cyber font-bold">{r.alpha}</td>
                <td className="py-2 pr-4"><Badge value={r.nc} /></td>
                <td className="py-2 pr-4"><Badge value={r.ber} invert decimals={4} /></td>
                <td className="py-2 pr-4 text-zinc-300">{r.psnr_embed.toFixed(2)} dB</td>
                <td className="py-2 pr-4 text-zinc-300">{r.ssim.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-zinc-700">
              <td colSpan={2} className="py-2 pr-4 text-zinc-400 font-semibold">Media</td>
              <td className="py-2 pr-4"><Badge value={avgNC} /></td>
              <td className="py-2 pr-4"><Badge value={avgBER} invert decimals={4} /></td>
              <td colSpan={2} />
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

// ─── COMPONENTE PRINCIPALE VISTABATCH ────────────────────────────────────────
export default function VistaBatch() {
  const [sorgente, setSorgente] = useState("sipi"); // "sipi" | "zip"
  const [fileWatermark, setFileWatermark] = useState(null);
  const [fileZip, setFileZip] = useState(null);
  const [nImmagini, setNImmagini] = useState(8);
  const [stato, setStato] = useState("idle"); // idle | running | done | error
  const [progressi, setProgressi] = useState([]);
  const [risultati, setRisultati] = useState([]);
  const [errore, setErrore] = useState(null);
  const [viewImg, setViewImg] = useState(null);
  const [totaleDaElaborare, setTotaleDaElaborare] = useState(0); // <-- AGGIUNTO PER LA PERCENTUALE ZIP
  const abortRef = useRef(null);

  const bottoneAttivo = fileWatermark && (sorgente === "sipi" || fileZip) && stato !== "running";

  const avviaAnalisi = useCallback(async () => {
    if (!fileWatermark) return;
    if (sorgente === "zip" && !fileZip) return;

    setStato("running");
    setProgressi([]);
    setRisultati([]);
    setViewImg(null);
    setErrore(null);
    setTotaleDaElaborare(0);

    const form = new FormData();
    form.append("watermark_image", fileWatermark);
    form.append("sorgente", sorgente);
    form.append("n_immagini", nImmagini);

    if (sorgente === "zip" && fileZip) {
      form.append("dataset_zip", fileZip);
    }

    const accumulati = [];

    try {
      const resp = await fetch("http://localhost:8000/api/batch", {
        method: "POST",
        body: form,
      });
      if (!resp.ok) throw new Error(`Errore server: ${resp.status}`);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop();

        for (const chunk of chunks) {
          if (!chunk.trim()) continue;
          const eventMatch = chunk.match(/^event: (.+)$/m);
          const dataMatch = chunk.match(/^data: (.+)$/m);
          if (!dataMatch) continue;

          const eventName = eventMatch?.[1] ?? "message";
          const payload = JSON.parse(dataMatch[1]);

          if (eventName === "start") {
            setTotaleDaElaborare(payload.total); // Legge il totale esatto dal backend!
          } else if (eventName === "progress") {
            setProgressi(prev => [...prev, payload]);
          } else if (eventName === "image_done") {
            accumulati.push(payload.result);
            setRisultati([...accumulati]);
            setViewImg(prev => prev ?? payload.result.name);
          } else if (eventName === "error") {
            throw new Error(payload.message);
          } else if (eventName === "done") {
            const finali = payload.results?.length >= accumulati.length ? payload.results : accumulati;
            setRisultati(finali);
            if (finali.length > 0) setViewImg(prev => prev ?? finali[0].name);
            setStato("done");
          }
        }
      }
      if (accumulati.length > 0) {
        setRisultati(accumulati);
        setStato("done");
      }
    } catch (err) {
      setErrore(err.message);
      setStato("error");
    }
  }, [fileWatermark, sorgente, fileZip, nImmagini]);

  // ─── CALCOLO PROGRESSO ───
  const risultatoSelezionato = risultati.find(r => r.name === viewImg) || risultati[0] || null;

  const totaleStep = totaleDaElaborare > 0 ? totaleDaElaborare : (sorgente === "sipi" ? nImmagini : 1);
  const saltati = progressi.filter(p => p.phase === "skipped").length;
  const completati = risultati.length + saltati;

  const percProgress = stato === "done"
    ? 100
    : (totaleStep > 0 ? (completati / totaleStep) * 100 : 0);

  return (
    <div className="max-w-5xl mx-auto px-8 py-10 animate-fade-in">

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-cyber/10 border border-cyber/25 flex items-center justify-center">
            <BarChart2 className="w-4 h-4 text-cyber" />
          </div>
          <h1 className="text-xl font-semibold text-zinc-100">Analisi Batch</h1>
        </div>
        <p className="text-sm text-zinc-500 ml-11">
          Analisi completa su dataset standard (USC-SIPI) o personalizzato: ricerca dell'α ottimale, test di robustezza agli attacchi e metriche aggregate.
        </p>
      </div>

      {/* Toggle sorgente */}
      <div className="flex gap-2 mb-6 p-1 rounded-xl bg-[#111] border border-panel-border w-fit">
        {[
          { id: "sipi", label: "USC-SIPI", sub: "8 immagini classiche" },
          { id: "zip", label: "Dataset ZIP", sub: "Carica immagini personalizzate" },
        ].map(({ id, label, sub }) => (
          <button
            key={id}
            onClick={() => { setSorgente(id); setRisultati([]); setStato("idle"); }}
            className={[
              "px-4 py-2.5 rounded-lg text-xs font-semibold transition-all flex flex-col items-start gap-0.5",
              sorgente === id
                ? "bg-cyber/15 border border-cyber/40 text-cyber"
                : "text-zinc-500 hover:text-zinc-300",
            ].join(" ")}
          >
            <span>{label}</span>
            <span className={`text-[10px] font-normal ${sorgente === id ? "text-cyber/60" : "text-zinc-600"}`}>{sub}</span>
          </button>
        ))}
      </div>

      {/* Configurazione */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="flex flex-col gap-2">
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider px-1">
            Watermark da usare
          </label>
          <DropZone
            onFile={f => { setFileWatermark(f); setRisultati([]); setStato("idle"); }}
            label="Trascina il logo/watermark qui"
            sublabel="Verrà inserito in tutte le immagini del dataset"
          />
        </div>

        <div className="flex flex-col gap-3">
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider px-1">
            {sorgente === "zip" ? "Carica il tuo Dataset" : "Impostazioni USC-SIPI"}
          </label>

          {sorgente === "zip" ? (
            <div className="flex flex-col gap-3 flex-1">
              <div className="border border-dashed border-panel-border rounded-xl p-4 flex flex-col items-center justify-center bg-[#111] hover:border-cyber/50 transition-colors">
                <input
                  type="file"
                  accept=".zip,application/zip,application/x-zip-compressed"
                  onChange={(e) => {
                    if (e.target.files?.[0]) {
                      setFileZip(e.target.files[0]);
                      setRisultati([]);
                      setStato("idle");
                    }
                  }}
                  className="w-full text-sm text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-bold file:bg-cyber/10 file:text-cyber hover:file:bg-cyber/20 cursor-pointer"
                />
              </div>
              {fileZip && (
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-cyber/5 border border-cyber/20">
                  <CheckCircle2 className="w-3.5 h-3.5 text-cyber shrink-0" />
                  <p className="text-xs text-zinc-400 truncate">{fileZip.name}</p>
                  <span className="text-[10px] text-zinc-600 ml-auto shrink-0">
                    {(fileZip.size / 1024 / 1024).toFixed(1)} MB
                  </span>
                </div>
              )}
              <div className="p-3 rounded-lg bg-[#111] flex items-start gap-2">
                <Info className="w-3.5 h-3.5 text-cyber/50 mt-0.5 shrink-0" />
                <p className="text-[11px] text-zinc-600 leading-relaxed">
                  Il backend estrarrà e ridimensionerà automaticamente a 512×512 le immagini contenute nello ZIP per permettere la scomposizione a blocchi.
                </p>
              </div>
            </div>
          ) : (
            <div className="flex-1 p-5 rounded-xl bg-panel border border-panel-border flex flex-col gap-4">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs text-zinc-400">Immagini USC-SIPI da usare</p>
                  <span className="text-sm font-bold text-cyber bg-cyber/10 border border-cyber/20 px-2.5 py-0.5 rounded-lg">
                    {nImmagini} / 8
                  </span>
                </div>
                <input
                  type="range" min={1} max={8} step={1}
                  value={nImmagini}
                  onChange={e => setNImmagini(parseInt(e.target.value))}
                  className="w-full h-1.5 appearance-none rounded-full cursor-pointer bg-zinc-800
                    [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4
                    [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full
                    [&::-webkit-slider-thumb]:bg-cyber [&::-webkit-slider-thumb]:cursor-pointer"
                />
                <div className="flex justify-between mt-1 text-[10px] text-zinc-600">
                  <span>1 (veloce)</span><span>8 (completo)</span>
                </div>
              </div>
              <div className="p-3 rounded-lg bg-[#111] flex items-start gap-2">
                <Info className="w-3.5 h-3.5 text-cyber/50 mt-0.5 shrink-0" />
                <p className="text-[11px] text-zinc-600 leading-relaxed">
                  Per ogni immagine vengono testati <strong className="text-zinc-500">{ALPHA_GRID.length} valori di α</strong> × 6 attacchi.
                  8 immagini richiedono ~1-2 minuti.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottone avvio */}
      <button
        disabled={!bottoneAttivo}
        onClick={avviaAnalisi}
        className={[
          "w-full flex items-center justify-center gap-2.5 py-3 rounded-xl font-semibold text-sm transition-all duration-200 mb-6",
          bottoneAttivo
            ? "bg-cyber text-black font-bold hover:shadow-cyber shadow-lg"
            : "bg-[#111] text-zinc-600 cursor-not-allowed",
        ].join(" ")}
      >
        {stato === "running" ? (
          <><Loader2 className="w-4 h-4 animate-spin" />Analisi in corso...</>
        ) : (
          <><Play className="w-4 h-4" />Avvia Analisi Batch</>
        )}
      </button>

      {/* Progress */}
      {(stato === "running" || (stato === "done" && risultati.length > 0)) && (
        <div className="mb-6 p-4 rounded-xl bg-panel border border-panel-border">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-zinc-400 font-medium">
              {stato === "done" ? "Analisi completata" : `Elaborazione in corso...`}
            </p>
            <span className="text-xs text-cyber font-bold">{percProgress > 100 ? 100 : percProgress.toFixed(0)}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-zinc-800 overflow-hidden">
            <div
              className="h-full bg-cyber rounded-full transition-all duration-500"
              style={{ width: `${percProgress > 100 ? 100 : percProgress}%` }}
            />
          </div>
          {stato === "running" && progressi.length > 0 && (
            <p className="text-[11px] text-zinc-600 mt-2">
              {(() => {
                const last = progressi[progressi.length - 1];
                return last.phase === "download"
                  ? `⬇ Download/Estrazione: ${last.image}`
                  : last.phase === "analysis"
                    ? `⚙ Analisi: ${last.image}`
                    : last.phase === "skipped"
                      ? `⚠ Saltata (Errore o non valida): ${last.image}`
                      : "";
              })()}
            </p>
          )}
          {/* Chip immagini completate */}
          {risultati.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {risultati.map((r, i) => (
                <span
                  key={i}
                  className="text-[10px] px-2 py-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 flex items-center gap-1"
                >
                  <CheckCircle2 className="w-2.5 h-2.5" />
                  {r.name}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Errore */}
      {errore && (
        <div className="mb-6 flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <p className="text-sm">{errore}</p>
        </div>
      )}

      {/* ─── RISULTATI ────────────────────────────────────────────────────── */}
      {risultati.length > 0 && (
        <>
          <Section
            title="Riepilogo Dataset"
            subtitle="Valori di Correlazione Normalizzata (NC) e parametro α ottimale per l'intero dataset"
          >
            <HeatmapNC risultati={risultati} />
          </Section>

          <Section
            title="Ricerca α Ottimale"
            subtitle={
              <span className="flex items-center gap-1.5 pt-1">
                <span>Funzione Obiettivo Multi-Criterio:</span>
                <span className="font-mono text-[11px] text-cyber bg-cyber/10 border border-cyber/20 px-2 py-0.5 rounded shadow-sm">
                  <span className="font-bold">Score</span> = (PSNR &ge; 30) ? (0.6 &times; NC<sub>medio</sub> + 0.4 &times; PSNR<sub>norm</sub>) : 0
                </span>
              </span>
            }
          >
            <div className="flex items-start gap-3 p-3 rounded-lg bg-[#0a0a0a] border border-zinc-800 mb-4">
              <Info className="w-3.5 h-3.5 text-cyber/60 mt-0.5 shrink-0" />
              <p className="text-[11px] text-zinc-500 leading-relaxed">
                La <strong>Funzione Obiettivo Multi-Criterio</strong> bilancia la robustezza agli attacchi (NC medio) e la qualità visiva (PSNR). Viene mantenuto un <strong>vincolo rigido</strong> che azzera il punteggio se il PSNR scende sotto i 30 dB (degrado inaccettabile), mentre il punteggio di qualità viene saturato a 40 dB (eccellenza visiva). Ciò permette all'algoritmo di trovare il punto di convergenza perfetto: la massima energia inseribile prima di intaccare in modo penalizzante l'invisibilità del watermark.
              </p>
            </div>
            <GraficoAlphaOttimale risultati={risultati} />
          </Section>

          <Section
            title="Analisi Dettagliata per Immagine"
            subtitle="Curva α e robustezza agli attacchi per ogni immagine del dataset"
          >
            <div className="flex flex-wrap gap-2 mb-5">
              {risultati.map(r => (
                <button
                  key={r.name}
                  onClick={() => setViewImg(r.name)}
                  className={[
                    "px-3 py-1.5 rounded-lg text-xs font-medium transition-all border",
                    viewImg === r.name
                      ? "bg-cyber/15 border-cyber/40 text-cyber"
                      : "bg-[#111] border-panel-border text-zinc-400 hover:border-zinc-600",
                  ].join(" ")}
                >
                  {r.name}
                </button>
              ))}
            </div>

            {risultatoSelezionato && (
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <p className="text-xs font-medium text-zinc-400 tracking-wider mb-3">
                    CURVA α — {risultatoSelezionato.name}
                  </p>
                  <CurvaAlpha risultato={risultatoSelezionato} />
                </div>
                <div>
                  <p className="text-xs font-medium text-zinc-400 tracking-wider mb-3">
                    ROBUSTEZZA AGLI ATTACCHI (α = {risultatoSelezionato.best_alpha})
                  </p>
                  <RadarAttacchi matrice={risultatoSelezionato.matrice} />
                </div>

                <div className="col-span-2">
                  <p className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-3">
                    Tabella attacchi — {risultatoSelezionato.name}
                  </p>
                  <table className="w-full text-xs border-collapse">
                    <thead>
                      <tr>
                        {["Attacco", "NC", "BER", "PSNR attacco"].map(h => (
                          <th key={h} className="text-left text-zinc-500 pb-2 pr-4 font-medium">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {risultatoSelezionato.matrice.map((m, i) => (
                        <tr key={i} className="border-t border-zinc-800/50">
                          <td className="py-2 pr-4 text-zinc-300">
                            <span className="flex items-center gap-2">
                              <span
                                className="w-2 h-2 rounded-full inline-block"
                                style={{ background: ATTACK_COLORS[m.attack] ?? "#888" }}
                              />
                              {ATTACK_LABELS[m.attack] ?? m.attack}
                            </span>
                          </td>
                          <td className="py-2 pr-4"><Badge value={m.nc} /></td>
                          <td className="py-2 pr-4"><Badge value={m.ber} invert decimals={4} /></td>
                          <td className="py-2 pr-4 text-zinc-400">{m.psnr_attack.toFixed(2)} dB</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </Section>

          <Section
            title="Caso Senza Attacco — Analisi Dettagliata"
            defaultOpen={true}
          >
            <AnalisiNoAttack risultati={risultati} />
          </Section>

          {stato === "done" && (
            <div className="flex justify-end mt-2">
              <button
                onClick={() => {
                  const blob = new Blob([JSON.stringify(risultati, null, 2)], { type: "application/json" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url; a.download = "batch_results.json"; a.click();
                }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#111] border border-panel-border text-zinc-400 hover:text-cyber text-xs font-medium transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                Esporta risultati JSON
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}