from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
import cv2
from typing import Tuple

DIM_BLOCCO: int = 8

def _robust_svd(matrix: np.ndarray):
    
    # 1. Pulisce eventuali valori NaN o Infiniti causati dagli attacchi
    if np.isnan(matrix).any() or np.isinf(matrix).any():
        matrix = np.nan_to_num(matrix)
        
    try:
        return np.linalg.svd(matrix, full_matrices=False)
    except np.linalg.LinAlgError:
        # 2. Se esplode, aggiunge un rumore impercettibile (1e-5) e riprova
        jitter = np.random.normal(0, 1e-5, matrix.shape)
        return np.linalg.svd(matrix + jitter, full_matrices=False)
    
def _in_float(img: NDArray[np.uint8]) -> NDArray[np.float64]:
    return img.astype(np.float64) / 255.0

def _in_uint8(img: NDArray[np.float64]) -> NDArray[np.uint8]:
    return np.clip(img * 255.0, 0.0, 255.0).astype(np.uint8)

def _in_grigio(img: NDArray) -> NDArray[np.uint8]:
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img.copy()

def embed_watermark(
    host: NDArray[np.uint8],
    watermark: NDArray[np.uint8],
    alpha: float = 0.1,
) -> Tuple[NDArray[np.uint8], NDArray[np.float64]]:
    host_grigio = _in_grigio(host)
    wm_grigio   = _in_grigio(watermark)
    alt, larg   = host_grigio.shape
    n_righe     = alt // DIM_BLOCCO
    n_colonne   = larg // DIM_BLOCCO
    # 1. Resize rigido a 64x64 (o n_colonne x n_righe) senza creare sfumature intermedie
    wm_ridimensionato = cv2.resize(
        wm_grigio, (n_colonne, n_righe), interpolation=cv2.INTER_NEAREST
    )
    # 2. Binarizzazione Hard: Uccide tutti i grigi rimasti (tutto ciò che è > 127 diventa 255)
    _, wm_ridimensionato = cv2.threshold(wm_ridimensionato, 127, 255, cv2.THRESH_BINARY)

    wm_float  = _in_float(wm_ridimensionato)
    img_float = _in_float(host_grigio)

    immagine_watermarked = img_float.copy()
    original_svs = np.zeros((n_righe, n_colonne), dtype=np.float64)

    for i in range(n_righe):
        for j in range(n_colonne):
            r0, r1 = i * DIM_BLOCCO, (i + 1) * DIM_BLOCCO
            c0, c1 = j * DIM_BLOCCO, (j + 1) * DIM_BLOCCO
            blocco = img_float[r0:r1, c0:c1]
            U, S, Vt = _robust_svd(blocco)
            original_svs[i, j] = S[0]
            S_mod    = S.copy()
            S_mod[0] += alpha * wm_float[i, j]
            immagine_watermarked[r0:r1, c0:c1] = U @ np.diag(S_mod) @ Vt

    # Chiave = stack di due matrici float64:
    #   layer 0 → S[0] originali
    #   layer 1 → wm_float (Ora è un binario matematico puro)
    chiave = np.stack([original_svs, wm_float], axis=-1)

    return _in_uint8(immagine_watermarked), chiave
def extract_watermark(
    image: NDArray[np.uint8],
    chiave: NDArray[np.float64],
    alpha: float = 0.1,
) -> NDArray[np.uint8]:
    if chiave.ndim == 2:
        original_svs = chiave
    else:
        original_svs = chiave[:, :, 0]

    img_grigio = _in_grigio(image)
    img_float  = _in_float(img_grigio)
    n_righe, n_colonne = original_svs.shape

    watermark_estratto = np.zeros((n_righe, n_colonne), dtype=np.float64)

    for i in range(n_righe):
        for j in range(n_colonne):
            r0, r1 = i * DIM_BLOCCO, (i + 1) * DIM_BLOCCO
            c0, c1 = j * DIM_BLOCCO, (j + 1) * DIM_BLOCCO
            blocco = img_float[r0:r1, c0:c1]
            _, S, _ = _robust_svd(blocco)
            watermark_estratto[i, j] = (S[0] - original_svs[i, j]) / alpha

    watermark_estratto = np.clip(watermark_estratto, 0.0, 1.0)
    return _in_uint8(watermark_estratto)

def extract_watermark_float(
    image: NDArray[np.uint8],
    chiave: NDArray[np.float64],
    alpha: float = 0.1,
) -> NDArray[np.float64]:
    if chiave.ndim == 2:
        original_svs = chiave
        wm_float_ref = None
    else:
        original_svs = chiave[:, :, 0]
        wm_float_ref = chiave[:, :, 1]

    img_grigio = _in_grigio(image)
    img_float  = _in_float(img_grigio)
    n_righe, n_colonne = original_svs.shape

    watermark_estratto = np.zeros((n_righe, n_colonne), dtype=np.float64)

    for i in range(n_righe):
        for j in range(n_colonne):
            r0, r1 = i * DIM_BLOCCO, (i + 1) * DIM_BLOCCO
            c0, c1 = j * DIM_BLOCCO, (j + 1) * DIM_BLOCCO
            blocco = img_float[r0:r1, c0:c1]
            _, S, _ = _robust_svd(blocco)
            watermark_estratto[i, j] = (S[0] - original_svs[i, j]) / alpha

    return np.clip(watermark_estratto, 0.0, 1.0)