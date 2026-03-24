from __future__ import annotations
import io
import base64
import logging
from typing import Annotated

import cv2
import numpy as np
from numpy.typing import NDArray
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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


@app.post(
    "/api/embed",
    summary="Inserisce il watermark nell'immagine",
)
async def embed_endpoint(
    host_image: Annotated[
        UploadFile,
        File(description="Immagine originale da proteggere"),
    ],
    watermark_image: Annotated[
        UploadFile,
        File(description="Il logo o watermark da nascondere"),
    ],
    alpha: Annotated[
        float,
        Form(description="Forza di inserimento. Valori tipici: 0.01 - 0.50"),
    ] = 0.1,
) -> JSONResponse:
    if alpha <= 0.0:
        raise HTTPException(status_code=422, detail="L'alpha deve essere un numero positivo.")

    # Lettura dei parametri
    host_bytes = await host_image.read()
    wm_bytes   = await watermark_image.read()
    host = _decode_upload(host_bytes)
    wm   = _decode_upload(wm_bytes)
    logger.info("Avvio Embedding — host %s, watermark %s, alpha=%.4f", host.shape, wm.shape, alpha)

    # Logica dell'SVD
    watermarked, original_svs = embed_watermark(host, wm, alpha=alpha)

    # Metriche
    psnr = calcola_psnr(host, watermarked)
    ssim = calcola_ssim(host, watermarked)
    logger.info("Embedding completato — PSNR=%.2f dB, SSIM=%.4f", psnr, ssim)

    return JSONResponse(
        content={
            "watermarked_image": _img_to_b64(watermarked),
            "key":               _array_to_b64(original_svs),
            "psnr":              round(psnr, 4),
            "ssim":              round(ssim, 6),
        }
    )


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


@app.post(
    "/api/extract",
    summary="Estrae il watermark",
)
async def extract_endpoint(
    watermarked_image: Annotated[
        UploadFile,
        File(description="L'immagine con watermark."),
    ],
    original_watermark: Annotated[
        UploadFile,
        File(description="Il logo originale (ci serve solo per calcolare quanto è accurata l'estrazione)."),
    ],
    key: Annotated[
        str,
        Form(description="La chiave segreta (in base64) ottenuta durante l'embed."),
    ],
    alpha: Annotated[
        float,
        Form(description="Forza alpha. Deve essere esattamente la stessa usata in fase di embed"),
    ] = 0.1,
) -> JSONResponse:
    if alpha <= 0.0:
        raise HTTPException(status_code=422, detail="L'alpha deve essere un numero positivo.")

    wm_bytes      = await watermarked_image.read()
    orig_wm_bytes = await original_watermark.read()
    wm_img  = _decode_upload(wm_bytes)
    orig_wm = _decode_upload(orig_wm_bytes)

    # Decodifico la chiave per riottenere la matrice originale dei valori singolari
    original_svs = _b64_to_array(key)
    logger.info("Avvio estrazione — immagine %s, chiave %s, alpha=%.4f", wm_img.shape, original_svs.shape, alpha)

    # Logica matematica di estrazione
    extracted = extract_watermark(wm_img, original_svs, alpha=alpha)

    # Calcolo quanto è sopravvissuto il watermark
    nc  = calcola_nc(orig_wm, extracted)
    ber = calcola_ber(orig_wm, extracted)
    logger.info("Estrazione completata — NC=%.4f, BER=%.4f", nc, ber)

    return JSONResponse(
        content={
            "extracted_watermark": _img_to_b64(extracted),
            "nc":                  round(nc, 6),
            "ber":                 round(ber, 6),
        }
    )


@app.get("/health", include_in_schema=False)
async def health_check() -> JSONResponse:
    return JSONResponse(content={"status": "Ok"})