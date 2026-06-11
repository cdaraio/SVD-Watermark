from __future__ import annotations
import base64
import io
import logging
from typing import Annotated

import cv2
import numpy as np
from numpy.typing import NDArray
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from core.batch import router as batch_router

from core.svd import embed_watermark, extract_watermark
from core.attacchi import (
    comprimi_jpeg,
    aggiungi_rumore_gaussiano,
    aggiungi_rumore_salt_pepper,
    ritaglia,
    ruota,
)
from core.metriche import calcola_psnr, calcola_ssim, calcola_nc, calcola_ber

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API Watermarking SVD",
    description="API per l'inserimento, attacco ed estrazione di watermark da immagine.",
    version="1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(batch_router)

def _decode_upload(data: bytes) -> NDArray[np.uint8]:
    # Decodifica i byte caricati in un array numpy (scala di grigi)
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise HTTPException(
            status_code=422,
            detail="Impossibile decodificare l'immagine. Assicurati che sia PNG, JPEG o BMP.",
        )
    return img


def _img_to_b64(img: NDArray[np.uint8]) -> str:
    # Trasforma l'immagine numpy in una stringa base64 da mandare al frontend
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("Errore durante la codifica PNG.")
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def _array_to_b64(arr: NDArray[np.float64]) -> str:
    # Salva la matrice dei valori singolari SVD in base64 (key)
    buf = io.BytesIO()
    np.save(buf, arr)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _b64_to_array(b64: str) -> NDArray[np.float64]:
    # Processo inverso: stringa base64 in array numpy dei valori singolari
    try:
        raw = base64.b64decode(b64)
        return np.load(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Chiave segreta non valida: {exc}",
        ) from exc


@app.post("/api/embed")
async def embed_endpoint(
    host_image: UploadFile = File(...),
    watermark_image: UploadFile = File(...),
    alpha: float = Form(0.1),
):
    host_bytes = await host_image.read()
    wm_bytes   = await watermark_image.read()
    
    host = _decode_upload(host_bytes)
    wm   = _decode_upload(wm_bytes)
    
    # 1. IL BUTTAFUORI: Calcoliamo la griglia esatta
    alt, larg = host.shape
    n_righe, n_colonne = alt // DIM_BLOCCO, larg // DIM_BLOCCO
    
    # 2. Rimpiccioliamo l'immagine dell'utente alla misura esatta
    wm_resized = cv2.resize(wm, (n_colonne, n_righe), interpolation=cv2.INTER_AREA)
    
    # 3. Forziamo il logo a diventare bit puri (0 o 255).
    # Usiamo THRESH_OTSU_INV per separare automaticamente il logo dallo sfondo
    # e far sì che il logo abbia energia (255) e lo sfondo sia spento (0).
    _, wm_binario = cv2.threshold(wm_resized, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Ora passiamo alla SVD una matrice perfetta (come la tua scacchiera)
    watermarked, original_svs = embed_watermark(host, wm_binario, alpha=alpha)

    psnr = calcola_psnr(host, watermarked)
    ssim = calcola_ssim(host, watermarked)

    return JSONResponse(
        content={
            "watermarked_image": _img_to_b64(watermarked),
            "key":               _array_to_b64(original_svs),
            "psnr":              round(psnr, 4),
            "ssim":              round(ssim, 6),
        }
    )

def _sanitize_watermark(wm_bytes: bytes, target_shape: Tuple[int, int]) -> NDArray[np.uint8]:
    """
    Pulisce, ridimensiona e binarizza il watermark caricato dall'utente.
    """
    # 1. Caricamento forzato in scala di grigi (ignora colori e trasparenza)
    nparr = np.frombuffer(wm_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    
    if img is None:
        raise HTTPException(status_code=422, detail="File watermark non valido.")

    # 2. Resize preciso (INTER_AREA è perfetto per ridimensionare loghi)
    img_resized = cv2.resize(img, target_shape, interpolation=cv2.INTER_AREA)

    # 3. Binarizzazione brutale (Otsu) per eliminare ogni grigio
    _, img_binary = cv2.threshold(img_resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return img_binary


_VALID_ATTACKS: list[str] = ["jpeg", "gaussian", "salt_pepper", "cropping", "rotation"]


@app.post(
    "/api/attack",
    summary="Applica un attacco simulato all'immagine",
)
async def attack_endpoint(
    image: Annotated[
        UploadFile,
        File(description="L'immagine su cui applicare l'attacco."),
    ],
    attack_type: Annotated[
        str,
        Form(description=f"Il tipo di attacco. Valori: {', '.join(_VALID_ATTACKS)}."),
    ],
    # Parametri specifici per i vari attacchi
    quality:      Annotated[int,   Form(description="[jpeg] Qualità (1-100).")] = 50,
    sigma:        Annotated[float, Form(description="[gaussian] Quantità di rumore.")] = 25.0,
    density:      Annotated[float, Form(description="[salt_pepper] Percentuale di pixel corrotti.")] = 0.05,
    crop_fraction:Annotated[float, Form(description="[cropping] Frazione da oscurare (0-1).")] = 0.1,
    angle:        Annotated[float, Form(description="[rotation] Angolo di rotazione in gradi.")] = 10.0,
) -> JSONResponse:
    if attack_type not in _VALID_ATTACKS:
        raise HTTPException(
            status_code=422,
            detail=f"Attacco non riconosciuto. Usa uno di questi: {_VALID_ATTACKS}.",
        )

    img_bytes = await image.read()
    img = _decode_upload(img_bytes)
    logger.info("Avvio attacco '%s' sull'immagine %s", attack_type, img.shape)

    # Mapping per chiamare la funzione giusta in base al tipo di attacco
    _dispatch = {
        "jpeg":        lambda i: comprimi_jpeg(i, quality),
        "gaussian":    lambda i: aggiungi_rumore_gaussiano(i, 0.0, sigma),
        "salt_pepper": lambda i: aggiungi_rumore_salt_pepper(i, density),
        "cropping":    lambda i: ritaglia(i, crop_fraction),
        "rotation":    lambda i: ruota(i, angle),
    }
    attacked = _dispatch[attack_type](img)

    return JSONResponse(
        content={
            "attacked_image": _img_to_b64(attacked),
            "attack_type":    attack_type,
        }
    )

@app.post("/api/extract")
async def extract_endpoint(
    watermarked_image: UploadFile = File(...),
    original_watermark: UploadFile = File(...),
    key: UploadFile = File(...)
):
    wm_bytes = await watermarked_image.read()
    orig_wm_bytes = await original_watermark.read()
    
    key_content = await key.read()
    key_str = key_content.decode("utf-8").strip().replace('"', '').replace("'", "")

    wm_img  = _decode_upload(wm_bytes)
    orig_wm = _decode_upload(orig_wm_bytes)

    original_svs = _b64_to_array(key_str)
    n_righe, n_colonne = original_svs.shape
    
    # 1. Riapplichiamo all'originale lo STESSO IDENTICO trattamento fatto nell'embed
    orig_wm_resized = cv2.resize(orig_wm, (n_colonne, n_righe), interpolation=cv2.INTER_AREA)
    _, orig_wm_binario = cv2.threshold(orig_wm_resized, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # 2. Estraiamo il segnale matematico (esce tra 0 e 255 ma con delle sfumature dovute al rumore)
    # L'estrazione rileva l'energia, quindi non serve INV qui.
    extracted = extract_watermark(wm_img, original_svs, alpha=0.1) # Usa il tuo alpha
    
    # 3. Forziamo anche il risultato estratto a essere Bit Puro
    _, extracted_binario = cv2.threshold(extracted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 4. Confronto matematico perfetto (Bianco/Nero vs Bianco/Nero)
    nc  = calcola_nc(orig_wm_binario, extracted_binario)
    ber = calcola_ber(orig_wm_binario, extracted_binario)

    return JSONResponse(
        content={
            "extracted_watermark": _img_to_b64(extracted_binario),
            "nc": round(float(nc), 6),
            "ber": round(float(ber), 6),
        }
    )