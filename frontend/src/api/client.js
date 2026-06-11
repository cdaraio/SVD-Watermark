const BASE = "/api"; 

// Controlla se la risposta HTTP ha dato errore e nel caso lancio eccezione
async function controllaErrore(risposta) {
  if (!risposta.ok) {
    let dettaglioErrore = risposta.statusText;
    try {
      // Provo a leggere il dettaglio dell'errore server
      const body = await risposta.json();
      dettaglioErrore = body.detail ?? JSON.stringify(body);
    } catch {
    }
    throw new Error(dettaglioErrore);
  }
}

// Invia i dati al backend per nascondere il watermark
export async function inserisciWatermark({ hostFile, watermarkFile, alpha }) {
  const datiForm = new FormData();
  datiForm.append("host_image", hostFile);
  datiForm.append("watermark_image", watermarkFile);
  datiForm.append("alpha", String(alpha));
  const risposta = await fetch(`${BASE}/embed`, { method: "POST", body: datiForm });
  await controllaErrore(risposta);
  return risposta.json();
}

// Richiesta persimulare un attacco sull'immagine
export async function applicaAttacco({ imageFile, attackType, params }) {
  const datiForm = new FormData();
  datiForm.append("image", imageFile);
  datiForm.append("attack_type", attackType);
  //parametri specifici dell'attacco
  for (const [chiave, valore] of Object.entries(params)) {
    datiForm.append(chiave, String(valore));
  }
  const risposta = await fetch(`${BASE}/attack`, { method: "POST", body: datiForm });
  await controllaErrore(risposta);
  return risposta.json();
}

// Invia i dati per l'estrazione 
export async function estraiWatermark({
  watermarkedFile,
  originalWatermarkFile,
  key,
  alpha,
}) {
  const datiForm = new FormData();
  datiForm.append("watermarked_image", watermarkedFile);
  datiForm.append("original_watermark", originalWatermarkFile);
  datiForm.append("alpha", String(alpha));

  // CORREZIONE: Non usare mai JSON.stringify sulla chiave!
  // La chiave è già una stringa pura base64.
  const chiaveBlob = new Blob([key], { type: "text/plain" });
  datiForm.append("key", chiaveBlob, "chiave.txt");

  const risposta = await fetch(`${BASE}/extract`, { 
    method: "POST", 
    body: datiForm 
  });
  
  if (!risposta.ok) {
    const errorDetail = await risposta.json().catch(() => ({}));
    console.error("Errore API:", errorDetail);
    throw new Error(errorDetail.detail?.[0]?.msg || errorDetail.detail || "Errore 422");
  }
  
  return risposta.json();
}