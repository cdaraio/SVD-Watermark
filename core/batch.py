from __future__ import annotations

import asyncio
import io
import json
import logging
import time
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
from core.confronto import (
    embed_lsb, extract_lsb,
    embed_dct, extract_dct,
    embed_dwt, extract_dwt,
    embed_svd_classica, extract_svd_classica,
)

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

# ─────────────────────────────────────────────────────────────────────────────
# CONFRONTO CON METODI CLASSICI (LSB, DCT, DWT, SVD classica)
# ─────────────────────────────────────────────────────────────────────────────

# Griglie di ricerca per calibrare ciascun metodo classico in modo che
# raggiunga (circa) lo stesso PSNR della nostra SVD a blocchi: senza questa
# calibrazione il confronto sarebbe scorretto (parametri con "unità" diverse
# a parità di alpha non producono la stessa invisibilità del watermark).
_ALPHA_GRID_DCT = [round(v, 1) for v in np.arange(1.0, 60.0, 1.0)]
_ALPHA_GRID_DWT = [round(v, 1) for v in np.arange(1.0, 60.0, 1.0)]
_ALPHA_GRID_SVD_CLASSICA = [round(v, 3) for v in np.arange(0.005, 0.3, 0.005)]


def _calibra_alpha(embed_fn, host, wm_pulito, target_psnr: float, griglia: list[float]) -> float:
    """Cerca, nella griglia data, l'alpha che porta il PSNR più vicino al target."""
    migliore, miglior_diff = griglia[0], float("inf")
    for a in griglia:
        try:
            watermarked, _ = embed_fn(host, wm_pulito, a)
        except Exception:
            continue
        psnr = calcola_psnr(host, watermarked)
        if np.isinf(psnr) or np.isnan(psnr):
            continue
        diff = abs(psnr - target_psnr)
        if diff < miglior_diff:
            miglior_diff, migliore = diff, a
    return migliore


def _confronta_metodi(
    host: np.ndarray,
    wm_pulito: np.ndarray,
    risultato_nostro: dict,
    matrice_nostro: list[dict],
) -> list[dict]:
    """
    Confronta la SVD a blocchi (già calcolata dal chiamante) con 4 metodi
    classici, calibrati per avere un PSNR di embedding simile (confronto equo).
    Ritorna una lista di dict, uno per metodo, con:
      - metriche aggregate (psnr, ssim, nc_no_attack, nc_mean_attacks, tempi)
      - "matrice": lista con il dettaglio per singolo attacco (nc, ber, psnr_attack)
    """
    target_psnr = risultato_nostro["psnr_embed"]

    metodi: list[dict] = []

    # --- SVD a blocchi: riusiamo i valori/matrice già noti ---
    metodi.append({
        "method": "svd_blocchi",
        "label": "SVD a blocchi",
        "alpha": risultato_nostro["alpha"],
        "psnr": risultato_nostro["psnr_embed"],
        "ssim": risultato_nostro["ssim_embed"],
        "nc_no_attack": risultato_nostro["nc_no_attack"],
        "ber_no_attack": risultato_nostro["ber_no_attack"],
        "nc_mean_attacks": risultato_nostro["nc_mean_attacks"],
        "embed_time_ms": risultato_nostro["embed_time_ms"],
        "extract_time_ms": risultato_nostro["extract_time_ms"],
        "matrice": matrice_nostro,  # [{attack, nc, ber, psnr_attack}, ...] già calcolata dal chiamante
    })

    _specifiche = [
        ("lsb", "LSB", embed_lsb, extract_lsb, 1.0, None),
        ("dct", "DCT (blocchi 8x8)", embed_dct, extract_dct, None, _ALPHA_GRID_DCT),
        ("dwt", "DWT (Haar 1 livello)", embed_dwt, extract_dwt, None, _ALPHA_GRID_DWT),
        ("svd_classica", "SVD classica (whole-image)", embed_svd_classica, extract_svd_classica, None, _ALPHA_GRID_SVD_CLASSICA),
    ]

    for nome_met, label, embed_fn, extract_fn, alpha_fisso, griglia in _specifiche:
        try:
            alpha = alpha_fisso if alpha_fisso is not None else _calibra_alpha(
                embed_fn, host, wm_pulito, target_psnr, griglia
            )

            t0 = time.perf_counter()
            watermarked, chiave = embed_fn(host, wm_pulito, alpha)
            embed_time_ms = (time.perf_counter() - t0) * 1000.0

            psnr = calcola_psnr(host, watermarked)
            if np.isinf(psnr) or np.isnan(psnr):
                psnr = 99.0
            ssim = calcola_ssim(host, watermarked)

            t0 = time.perf_counter()
            estratto = extract_fn(watermarked, chiave, alpha)
            extract_time_ms = (time.perf_counter() - t0) * 1000.0
            _, est_bin = cv2.threshold(estratto, 127, 255, cv2.THRESH_BINARY)

            nc_no = calcola_nc(wm_pulito, est_bin)
            ber_no = calcola_ber(wm_pulito, est_bin)

            matrice_metodo: list[dict] = [{
                "attack": "no_attack",
                "nc": round(float(nc_no), 5),
                "ber": round(float(ber_no), 5),
                "psnr_attack": 99.0,
            }]

            for nome_attacco, fn_att in ATTACCHI.items():
                if nome_attacco == "no_attack":
                    continue
                attaccata = fn_att(watermarked)
                est_att = extract_fn(attaccata, chiave, alpha)
                _, est_att_bin = cv2.threshold(est_att, 127, 255, cv2.THRESH_BINARY)

                nc_att = calcola_nc(wm_pulito, est_att_bin)
                ber_att = calcola_ber(wm_pulito, est_att_bin)
                psnr_att = calcola_psnr(watermarked, attaccata)
                if np.isinf(psnr_att) or np.isnan(psnr_att):
                    psnr_att = 99.0

                matrice_metodo.append({
                    "attack": nome_attacco,
                    "nc": round(float(nc_att), 5),
                    "ber": round(float(ber_att), 5),
                    "psnr_attack": round(float(psnr_att), 3),
                })

            nc_medio = float(np.mean([m["nc"] for m in matrice_metodo if m["attack"] != "no_attack"]))

            metodi.append({
                "method": nome_met,
                "label": label,
                "alpha": alpha,
                "psnr": round(float(psnr), 3),
                "ssim": round(float(ssim), 5),
                "nc_no_attack": round(float(nc_no), 5),
                "ber_no_attack": round(float(ber_no), 5),
                "nc_mean_attacks": round(nc_medio, 5),
                "embed_time_ms": round(embed_time_ms, 3),
                "extract_time_ms": round(extract_time_ms, 3),
                "matrice": matrice_metodo,
            })
        except Exception as e:
            logger.warning("Confronto metodi: errore su %s: %s", nome_met, e)
            metodi.append({
                "method": nome_met, "label": label, "errore": str(e),
            })

    return metodi



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
            psnr_norm = np.clip((psnr - 35.0) / 10.0, 0.0, 1.0)
            score = 0.6 * nc_medio + 0.4 * psnr_norm
            print(f"{nome} | alpha={alpha:.2f} | psnr={psnr:.1f} | nc_medio={nc_medio:.3f} | psnr_norm={psnr_norm:.3f} | score={score:.3f}")

        else:
            score = 0.0

        if score > best_score:
            best_score = score
            best_alpha = alpha

    # --- CALCOLO MATRICE FINALE (con timing per l'analisi prestazionale) ---
    t0 = time.perf_counter()
    watermarked_best, chiave_best = embed_watermark(host, wm_pulito, alpha=best_alpha)
    embed_time_ms = (time.perf_counter() - t0) * 1000.0

    psnr_embed = calcola_psnr(host, watermarked_best)
    if np.isinf(psnr_embed) or np.isnan(psnr_embed):
        psnr_embed = 99.0
    ssim_embed = calcola_ssim(host, watermarked_best)

    t0 = time.perf_counter()
    estratto_best = extract_watermark(watermarked_best, chiave_best, alpha=best_alpha)
    extract_time_ms = (time.perf_counter() - t0) * 1000.0
    _, est_best_bin = cv2.threshold(estratto_best, 127, 255, cv2.THRESH_BINARY)

    nc_no_attack = calcola_nc(wm_pulito, est_best_bin)
    ber_no_attack = calcola_ber(wm_pulito, est_best_bin)

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

    nc_mean_attacks = float(np.mean([m["nc"] for m in matrice]))

    risultato_nostro = {
        "alpha": best_alpha,
        "psnr_embed": round(float(psnr_embed), 3),
        "ssim_embed": round(float(ssim_embed), 5),
        "nc_no_attack": round(float(nc_no_attack), 5),
        "ber_no_attack": round(float(ber_no_attack), 5),
        "nc_mean_attacks": round(nc_mean_attacks, 5),
        "embed_time_ms": round(embed_time_ms, 3),
        "extract_time_ms": round(extract_time_ms, 3),
    }

    # --- CONFRONTO CON METODI CLASSICI (LSB, DCT, DWT, SVD classica) ---
    confronto_metodi = _confronta_metodi(host, wm_pulito, risultato_nostro, matrice)

    return {
        "name":        nome,
        "best_alpha":  best_alpha,
        "curva_alpha": curva_alpha,
        "matrice":     matrice,
        "tempi": {
            "embed_ms": risultato_nostro["embed_time_ms"],
            "extract_ms": risultato_nostro["extract_time_ms"],
        },
        "confronto_metodi": confronto_metodi,
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
        t_batch_inizio = time.perf_counter()
        tempo_download_totale = 0.0
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

                    t_dl_inizio = time.perf_counter()  # <-- 1. Avvia cronometro download
                    
                    host = await _scarica_immagine(client, url)
                    await asyncio.sleep(1.0) # Pausa anti-spam
                    
                    tempo_download_totale += (time.perf_counter() - t_dl_inizio)  # <-- 2. Salva tempo
                    
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

        tempo_totale_batch_sec = time.perf_counter() - t_batch_inizio
        
        # --- CALCOLO PURO ---
        tempo_calcolo_puro_sec = tempo_totale_batch_sec - tempo_download_totale
        
        analisi_tempi = _analisi_tempi_batch(risultati, tempo_totale_batch_sec)
        
        # --- SALVATAGGIO NEL JSON ---
        analisi_tempi["tempo_download_sec"] = round(tempo_download_totale, 2)
        analisi_tempi["tempo_calcolo_puro_sec"] = round(tempo_calcolo_puro_sec, 2)
        
        print(f"\n{'='*50}")
        print(f"⏱️  TEMPO LORDO: {tempo_totale_batch_sec:.2f} s")
        print(f"🌐 TEMPO RETE/PAUSE: {tempo_download_totale:.2f} s")
        print(f"🚀 TEMPO CALCOLO PURO (M1): {tempo_calcolo_puro_sec:.2f} s")
        print(f"{'='*50}\n")
        
        confronto_metodi_dataset = _aggrega_confronto_metodi(risultati)
        takeaways = _genera_takeaways(risultati, analisi_tempi)

        yield _sse("done", {
            "results": risultati,
            "analisi_tempi": analisi_tempi,
            "confronto_metodi_dataset": confronto_metodi_dataset,
            "takeaways": takeaways,
        })

    return StreamingResponse(genera(), media_type="text/event-stream")


# ─────────────────────────────────────────────────────────────────────────────
# CONFRONTO METODI AGGREGATO SU TUTTO IL DATASET (non su una sola immagine)
# ─────────────────────────────────────────────────────────────────────────────
def _aggrega_confronto_metodi(risultati: list[dict]) -> list[dict]:
    """
    Media, per ciascun metodo e ciascun attacco, NC/BER/PSNR su TUTTE le
    immagini del dataset
    """
    # raccolgo, per ogni (metodo, attacco): lista di nc/ber di tutte le immagini
    per_metodo: dict[str, dict] = {}
    for r in risultati:
        for m in r.get("confronto_metodi", []):
            if "errore" in m:
                continue
            voce = per_metodo.setdefault(m["method"], {
                "label": m["label"], "alpha": [], "psnr": [], "ssim": [],
                "embed_time_ms": [], "extract_time_ms": [],
                "per_attacco": {},
            })
            voce["alpha"].append(m["alpha"])
            voce["psnr"].append(m["psnr"])
            voce["ssim"].append(m["ssim"])
            voce["embed_time_ms"].append(m["embed_time_ms"])
            voce["extract_time_ms"].append(m["extract_time_ms"])
            for att in m.get("matrice", []):
                lst = voce["per_attacco"].setdefault(att["attack"], {"nc": [], "ber": []})
                lst["nc"].append(att["nc"])
                lst["ber"].append(att["ber"])

    risultato: list[dict] = []
    for metodo, voce in per_metodo.items():
        matrice = [
            {
                "attack": attacco,
                "nc_medio": round(float(np.mean(vals["nc"])), 5),
                "ber_medio": round(float(np.mean(vals["ber"])), 5),
                "n_immagini": len(vals["nc"]),
            }
            for attacco, vals in voce["per_attacco"].items()
        ]
        risultato.append({
            "method": metodo,
            "label": voce["label"],
            "alpha_medio": round(float(np.mean(voce["alpha"])), 4),
            "psnr_medio": round(float(np.mean(voce["psnr"])), 3),
            "ssim_medio": round(float(np.mean(voce["ssim"])), 5),
            "embed_time_ms_medio": round(float(np.mean(voce["embed_time_ms"])), 3),
            "extract_time_ms_medio": round(float(np.mean(voce["extract_time_ms"])), 3),
            "n_immagini": len(voce["alpha"]),
            "matrice": matrice,
        })
    return risultato


# ─────────────────────────────────────────────────────────────────────────────
# ANALISI TEMPI (pipeline batch) + TAKEAWAY PER LA SLIDE FINALE
# ─────────────────────────────────────────────────────────────────────────────
def _analisi_tempi_batch(risultati: list[dict], tempo_totale_batch_sec: float) -> dict:
    """Riassume i tempi computazionali della pipeline: per immagine e per l'intero batch."""
    if not risultati:
        return {"tempo_totale_batch_sec": round(tempo_totale_batch_sec, 3)}

    embed_ms = [r["tempi"]["embed_ms"] for r in risultati if "tempi" in r]
    extract_ms = [r["tempi"]["extract_ms"] for r in risultati if "tempi" in r]

    # --- Media dei tempi per METODO su TUTTE le immagini del dataset ---
    tempi_per_metodo: dict[str, list[float]] = {}
    for r in risultati:
        for m in r.get("confronto_metodi", []):
            if "embed_time_ms" in m and "extract_time_ms" in m:
                tempi_per_metodo.setdefault(m["method"], []).append(
                    m["embed_time_ms"] + m["extract_time_ms"]
                )
    tempi_per_metodo_medi = {
        metodo: {
            "tempo_medio_ms": round(float(np.mean(vals)), 2),
            "tempo_min_ms": round(float(np.min(vals)), 2),
            "tempo_max_ms": round(float(np.max(vals)), 2),
            "n_immagini": len(vals),
        }
        for metodo, vals in tempi_per_metodo.items()
    }

    return {
        "n_immagini": len(risultati),
        "tempo_totale_batch_sec": round(tempo_totale_batch_sec, 3),
        "tempo_medio_per_immagine_sec": round(tempo_totale_batch_sec / len(risultati), 3),
        "embed_ms_medio": round(float(np.mean(embed_ms)), 3) if embed_ms else None,
        "extract_ms_medio": round(float(np.mean(extract_ms)), 3) if extract_ms else None,
        "tempi_per_metodo": tempi_per_metodo_medi,
        # NB: il tempo per immagine include l'intera ricerca dell'alpha ottimale
        # (griglia di ~50 valori x 6 attacchi) + il confronto con i 4 metodi
        # classici; embed_ms/extract_ms sopra si riferiscono invece alla
        # singola operazione di embed/extract con l'alpha ottimale già trovato,
        # mediata su tutte le immagini elaborate (non su una sola).
    }


def _genera_takeaways(risultati: list[dict], analisi_tempi: dict) -> list[str]:
    """Genera 5-6 takeaway sintetici pronti per una slide finale."""
    if not risultati:
        return ["Nessun risultato disponibile per generare i takeaway."]

    alphas = [r["best_alpha"] for r in risultati]
    nc_no_attack = [m["nc"] for r in risultati for m in r["matrice"] if m["attack"] == "no_attack"]
    nc_medi = [float(np.mean([m["nc"] for m in r["matrice"]])) for r in risultati]

    # Attacco più critico (NC medio più basso) sul dataset
    per_attacco: dict[str, list[float]] = {}
    for r in risultati:
        for m in r["matrice"]:
            per_attacco.setdefault(m["attack"], []).append(m["nc"])
    attacco_peggiore = min(per_attacco.items(), key=lambda kv: np.mean(kv[1]))
    attacco_migliore = max(per_attacco.items(), key=lambda kv: np.mean(kv[1]))

    # Confronto medio con i metodi classici (nc_mean_attacks) sull'ultimo alpha calibrato
    metodi_medi: dict[str, list[float]] = {}
    for r in risultati:
        for m in r.get("confronto_metodi", []):
            if "nc_mean_attacks" in m:
                metodi_medi.setdefault(m["label"], []).append(m["nc_mean_attacks"])
    metodi_ordinati = sorted(
        ((label, float(np.mean(v))) for label, v in metodi_medi.items()),
        key=lambda kv: kv[1], reverse=True,
    )
    nostro_label = "SVD a blocchi"
    nostro_rank = next((i + 1 for i, (l, _) in enumerate(metodi_ordinati) if l == nostro_label), None)

    takeaways = [
        f"Configurazione ottimale: α medio ≈ {np.mean(alphas):.2f} (range {min(alphas):.2f}-{max(alphas):.2f} sul dataset), "
        f"selezionato massimizzando robustezza (NC) a vincolo PSNR ≥ 30 dB.",

        f"Qualità visiva: NC medio senza attacchi ≈ {np.mean(nc_no_attack):.3f}, "
        f"NC medio su tutti gli attacchi ≈ {np.mean(nc_medi):.3f} — watermark recuperabile con alta affidabilità.",

        f"Robustezza differenziata: attacco più critico '{ATTACK_labels_it(attacco_peggiore[0])}' "
        f"(NC medio {np.mean(attacco_peggiore[1]):.3f}), più tollerato '{ATTACK_labels_it(attacco_migliore[0])}' "
        f"(NC medio {np.mean(attacco_migliore[1]):.3f}).",

        (
            f"Confronto con metodi classici: la SVD a blocchi si posiziona al {nostro_rank}° posto su "
            f"{len(metodi_ordinati)} metodi per NC medio, "
            + ", ".join(f"{l} {v:.3f}" for l, v in metodi_ordinati)
            + "."
        ) if metodi_ordinati else "Confronto con metodi classici non disponibile.",

        f"Prestazioni: tempo medio di elaborazione per immagine ≈ {analisi_tempi.get('tempo_medio_per_immagine_sec', 0):.2f}s "
        f"(ricerca α + confronto metodi), embed/extract con α ottimale ≈ "
        f"{analisi_tempi.get('embed_ms_medio', 0):.1f}/{analisi_tempi.get('extract_ms_medio', 0):.1f} ms — "
        f"compatibile con un uso quasi interattivo su singola immagine.",

        "Limiti e sviluppi futuri: la SVD classica richiede di conservare l'intera base del watermark "
        "(problema di sicurezza noto in letteratura); il metodo LSB è fragile a qualunque attacco lossy; "
        "sviluppi futuri: watermarking adattivo per-blocco (α variabile in base al contenuto locale) "
        "e test su dataset più ampi/eterogenei.",
    ]
    return takeaways


def ATTACK_labels_it(nome_attacco: str) -> str:
    return {
        "no_attack": "nessun attacco",
        "jpeg": "compressione JPEG",
        "gaussian": "rumore gaussiano",
        "salt_pepper": "rumore salt & pepper",
        "cropping": "ritaglio",
        "rotation": "rotazione",
    }.get(nome_attacco, nome_attacco)