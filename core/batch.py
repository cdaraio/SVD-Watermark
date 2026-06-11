from __future__ import annotations

import asyncio
import io
import json
import logging
import zipfile
from typing import Annotated, AsyncGenerator, Optional

import cv2
import httpx
import numpy as np
from PIL import Image
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from core.svd import embed_watermark, extract_watermark_float
from core.attacchi import (
    comprimi_jpeg,
    aggiungi_rumore_gaussiano,
    aggiungi_rumore_salt_pepper,
    ritaglia,
    ruota,
)
from core.metriche import calcola_psnr, calcola_ssim, calcola_nc, calcola_ber

logger = logging.getLogger(__name__)
router = APIRouter()

USC_SIPI_URLS: list[str] = [
    "https://sipi.usc.edu/database/download.php?vol=misc&img=4.2.04",     # 1. Lena
    "https://sipi.usc.edu/database/download.php?vol=misc&img=4.2.03",     # 2. Baboon
    "https://sipi.usc.edu/database/download.php?vol=misc&img=4.2.07",     # 3. Peppers
    "https://sipi.usc.edu/database/download.php?vol=misc&img=4.2.05",     # 4. Airplane
    "https://sipi.usc.edu/database/download.php?vol=misc&img=4.2.06",     # 5. Sailboat
    "https://sipi.usc.edu/database/download.php?vol=misc&img=4.2.01",     # 6. Splash
    "https://sipi.usc.edu/database/download.php?vol=misc&img=4.2.02",     # 7. Female
    "https://sipi.usc.edu/database/download.php?vol=textures&img=1.1.01", # 8. Texture Bark
]

IMAGE_NAMES = [
    "Lena", "Baboon", "Peppers", "Airplane",
    "Sailboat", "Splash", "Female", "Texture_Bark",
]

FORMATI_SUPPORTATI = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

ALPHA_GRID = [round(v, 2) for v in np.arange(0.01, 0.51, 0.01)]

ATTACCHI: dict[str, callable] = {
    "no_attack":   lambda img: img.copy(),
    "jpeg":        lambda img: comprimi_jpeg(img, quality=50),
    "gaussian":    lambda img: aggiungi_rumore_gaussiano(img, 0.0, 25.0),
    "salt_pepper": lambda img: aggiungi_rumore_salt_pepper(img, 0.05),
    "cropping":    lambda img: ritaglia(img, frazione_ritaglio=0.10),
    "rotation":    lambda img: ruota(img, angolo=10.0),
}

def _decode_bytes(data: bytes) -> np.ndarray:
    import numpy as np
    import cv2

    arr = np.frombuffer(data, dtype=np.uint8)
    # Carichiamo leggendo TUTTI i canali (anche l'Alpha)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)

    if img is None:
        return None

    # Se ha 4 canali (PNG con Trasparenza)
    if len(img.shape) == 3 and img.shape[2] == 4:
        bgr = img[:, :, :3]
        alpha = img[:, :, 3]
        # Creiamo un foglio bianco
        sfondo = np.ones_like(bgr, dtype=np.uint8) * 255
        
        # Incolliamo il logo sul foglio bianco usando la trasparenza come colla
        alpha_factor = alpha.astype(np.float32) / 255.0
        alpha_factor = np.stack([alpha_factor]*3, axis=-1)
        
        img_fusa = bgr * alpha_factor + sfondo * (1.0 - alpha_factor)
        return cv2.cvtColor(img_fusa.astype(np.uint8), cv2.COLOR_BGR2GRAY)

    # Se ha 3 canali (JPEG)
    elif len(img.shape) == 3 and img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Se è già in scala di grigi
    return img

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

def _estrai_immagini_zip(zip_bytes: bytes) -> list[tuple[str, np.ndarray]]:
    """Apre uno ZIP, estrae immagini valide e le ridimensiona a 512x512."""
    risultati = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        voci = sorted(zf.namelist())
        for voce in voci:
            if voce.endswith("/"):
                continue  # è una directory
            estensione = "." + voce.rsplit(".", 1)[-1].lower() if "." in voce else ""
            if estensione not in FORMATI_SUPPORTATI:
                continue
            try:
                dati = zf.read(voce)
                img  = _decode_bytes(dati)
                if img is None:
                    continue
                # Normalizza a 512x512 per garantire blocchi 8x8
                if img.shape != (512, 512):
                    img = cv2.resize(img, (512, 512), interpolation=cv2.INTER_AREA)
                
                # Questa riga taglia il '.jpg' lasciando solo 'astronomica_01'
                nome = voce.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                risultati.append((nome, img))
            except Exception as e:
                logger.warning("ZIP: errore su %s: %s", voce, e)
    return risultati

async def _scarica_immagine(client: httpx.AsyncClient, url: str) -> np.ndarray | None:
    try:
        r = await client.get(url, timeout=20, follow_redirects=True)
        r.raise_for_status()
        img_pil = Image.open(io.BytesIO(r.content)).convert("L")
        return np.array(img_pil, dtype=np.uint8)
    except Exception as e:
        logger.warning("Download fallito per %s: %s", url, e)
        return None

def _nc_float(wm_float_ref: np.ndarray, estratto_float: np.ndarray) -> float:
    a = wm_float_ref.ravel()
    b = estratto_float.ravel()
    den = np.linalg.norm(a) * np.linalg.norm(b)
    if den < 1e-10:
        return 0.0
    return float(np.dot(a, b) / den)

def _ber_float(wm_float_ref: np.ndarray, estratto_float: np.ndarray) -> float:
    # Binarizza l'originale (soglia 0.5 è ok perché è già binario)
    orig_bin = (wm_float_ref >= 0.5).astype(np.uint8)
    
    # SOGLIA DINAMICA: Usiamo la media dell'estratto per binarizzare (adattamento al rumore)
    soglia_est = np.mean(estratto_float)
    est_bin  = (estratto_float >= soglia_est).astype(np.uint8)
    
    return float(np.count_nonzero(orig_bin != est_bin) / orig_bin.size)

def _analizza_immagine(
    host: np.ndarray,
    wm: np.ndarray,
    nome: str,
) -> dict:
    from core.svd import embed_watermark, extract_watermark, DIM_BLOCCO
    import cv2
    import numpy as np

    alt, larg = host.shape
    n_righe = alt // DIM_BLOCCO
    n_colonne = larg // DIM_BLOCCO

    # PREPARAZIONE LOGO: Resize e Inversione per loghi con sfondo chiaro
    wm_resized = cv2.resize(wm, (n_colonne, n_righe), interpolation=cv2.INTER_AREA)
    _, wm_pulito = cv2.threshold(wm_resized, 127, 255, cv2.THRESH_BINARY_INV)

    curva_alpha: list[dict] = []
    best_alpha = ALPHA_GRID[0]
    best_score = -1.0

    for alpha in ALPHA_GRID:
        watermarked, chiave = embed_watermark(host, wm_pulito, alpha=alpha)
        psnr = calcola_psnr(host, watermarked)
        if np.isinf(psnr) or np.isnan(psnr):
            psnr = 99.0
        ssim = calcola_ssim(host, watermarked)

        # ESTRAZIONE A SOGLIA FISSA (Nessuna normalizzazione del rumore)
        estratto = extract_watermark(watermarked, chiave, alpha=alpha)
        _, est_bin = cv2.threshold(estratto, 127, 255, cv2.THRESH_BINARY)

        nc_no  = calcola_nc(wm_pulito, est_bin)
        ber_no = calcola_ber(wm_pulito, est_bin)

        ncs = []
        for _, fn_att in ATTACCHI.items():
            attaccata = fn_att(watermarked)
            est_att = extract_watermark(attaccata, chiave, alpha=alpha)
            _, est_att_bin = cv2.threshold(est_att, 127, 255, cv2.THRESH_BINARY)
            ncs.append(calcola_nc(wm_pulito, est_att_bin))
            
        nc_medio = float(np.mean(ncs))

        curva_alpha.append({
            "alpha": alpha,
            "psnr": round(psnr, 3),
            "ssim": round(ssim, 5),
            "nc_no_attack": round(float(nc_no), 5),
            "ber_no_attack": round(float(ber_no), 5),
            "nc_mean_attacks": round(nc_medio, 5),
        })

        # FUNZIONE OBIETTIVO BILANCIATA
        if psnr >= 30.0:
            psnr_norm = np.clip((psnr - 30.0) / 10.0, 0.0, 1.0)
            score = 0.6 * nc_medio + 0.4 * psnr_norm
            print(f"{nome} | alpha={alpha:.2f} | psnr={psnr:.1f} | nc_medio={nc_medio:.3f} | psnr_norm={psnr_norm:.3f} | score={score:.3f}")

        else:
            score = 0.0

        if score > best_score:
            best_score = score
            best_alpha = alpha

    # --- CALCOLO MATRICE FINALE ---
    watermarked_best, chiave_best = embed_watermark(host, wm_pulito, alpha=best_alpha)
    matrice: list[dict] = []
    
    for nome_att, fn_att in ATTACCHI.items():
        attaccata = fn_att(watermarked_best)
        est_att = extract_watermark(attaccata, chiave_best, alpha=best_alpha)
        _, est_att_bin = cv2.threshold(est_att, 127, 255, cv2.THRESH_BINARY)
        
        nc  = calcola_nc(wm_pulito, est_att_bin)
        ber = calcola_ber(wm_pulito, est_att_bin)
            
        psnr_att = calcola_psnr(watermarked_best, attaccata)
        if np.isinf(psnr_att) or np.isnan(psnr_att):
            psnr_att = 99.0
            
        matrice.append({
            "attack": nome_att,
            "nc":   round(float(nc), 5),
            "ber":  round(float(ber), 5),
            "psnr_attack": round(psnr_att, 3),
        })

    return {
        "name":        nome,
        "best_alpha":  best_alpha,
        "curva_alpha": curva_alpha,
        "matrice":     matrice,
    }

@router.post("/api/batch")
async def batch(
    watermark_image: Annotated[UploadFile, File(description="Watermark da usare per tutte le immagini")],
    sorgente:        Annotated[str, Form(description="'sipi' oppure 'zip'")] = "sipi",
    n_immagini:      Annotated[int, Form(description="Quante immagini USC-SIPI usare (1-8)")] = 8,
    dataset_zip:     Optional[UploadFile] = File(default=None, description="ZIP con immagini custom"),
) -> StreamingResponse:
    wm_bytes = await watermark_image.read()
    wm = _decode_bytes(wm_bytes)
    if wm is None:
        async def err():
            yield _sse("error", {"message": "Watermark non valido"})
        return StreamingResponse(err(), media_type="text/event-stream")

    if sorgente == "zip":
        if dataset_zip is None:
            async def err():
                yield _sse("error", {"message": "File ZIP mancante. Seleziona il file e riprova."})
            return StreamingResponse(err(), media_type="text/event-stream")
            
        zip_bytes = await dataset_zip.read()
        immagini_lista = _estrai_immagini_zip(zip_bytes)
        if not immagini_lista:
            async def err():
                yield _sse("error", {"message": "Il file ZIP caricato è vuoto o non contiene immagini valide (solo PNG, JPG, TIFF)."})
            return StreamingResponse(err(), media_type="text/event-stream")
        totale = len(immagini_lista)
    else:
        # Modalità USC-SIPI pura
        n_immagini = int(np.clip(n_immagini, 1, len(USC_SIPI_URLS)))
        immagini_lista = None
        totale = n_immagini

    async def genera() -> AsyncGenerator[str, None]:
        risultati: list[dict] = []
        yield _sse("start", {"total": totale, "alpha_grid": ALPHA_GRID, "sorgente": sorgente})

        if immagini_lista is not None:
            # ── MODALITÀ ZIP (Immagini Locali) ──
            for idx, (nome, host) in enumerate(immagini_lista):
                yield _sse("progress", {
                    "step": idx + 1, "total": totale,
                    "image": nome, "phase": "analysis",
                })
                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(None, _analizza_immagine, host, wm, nome)
                risultati.append(res)
                yield _sse("image_done", {"result": res, "index": idx})
        else:
            # ── MODALITÀ USC-SIPI (Download con Anti-Spam) ──
            async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}) as client:
                for idx in range(n_immagini):
                    url  = USC_SIPI_URLS[idx]
                    nome = IMAGE_NAMES[idx]
                    yield _sse("progress", {
                        "step": idx + 1, "total": totale,
                        "image": nome, "phase": "download",
                    })

                    host = await _scarica_immagine(client, url)
                    await asyncio.sleep(1.0) # Pausa anti-spam
                    
                    if host is None:
                        yield _sse("progress", {
                            "step": idx + 1, "total": totale,
                            "image": nome, "phase": "skipped",
                        })
                        continue

                    yield _sse("progress", {
                        "step": idx + 1, "total": totale,
                        "image": nome, "phase": "analysis",
                    })

                    loop = asyncio.get_event_loop()
                    res = await loop.run_in_executor(None, _analizza_immagine, host, wm, nome)
                    risultati.append(res)
                    yield _sse("image_done", {"result": res, "index": idx})

        yield _sse("done", {"results": risultati})

    return StreamingResponse(genera(), media_type="text/event-stream")