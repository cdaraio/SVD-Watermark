from __future__ import annotations

"""
Implementazioni "didattiche" di 4 metodi di watermarking classici,
usate SOLO per contestualizzare/confrontare il contributo del progetto
(SVD a blocchi, vedi core/svd.py) con le tecniche più note in letteratura:

    - LSB  (Least Significant Bit)
    - DCT  (Discrete Cosine Transform, block-based, stile JPEG)
    - DWT  (Discrete Wavelet Transform, Haar 1 livello, fatta a mano)
    - SVD classica (whole-image, metodo Liu & Tan 2002)

Ogni metodo espone due funzioni con la stessa "forma" già usata in core/svd.py:

    embed_xxx(host, watermark, alpha) -> (watermarked_uint8, chiave)
    extract_xxx(image, chiave, alpha) -> extracted_uint8 (0/255, grezzo)

così da poter riusare calcola_psnr / calcola_ssim / calcola_nc / calcola_ber
di core/metriche.py senza modifiche.
"""

from typing import Tuple
import numpy as np
from numpy.typing import NDArray
import cv2

from core.svd import DIM_BLOCCO, _robust_svd, _in_grigio, _in_float, _in_uint8


def _wm_a_griglia(wm: NDArray[np.uint8], n_righe: int, n_colonne: int) -> NDArray[np.float64]:
    """Ridimensiona e binarizza il watermark alla griglia (n_righe x n_colonne),
    restituendo valori float in {0, 1}. Stessa logica usata in core/svd.py."""
    wm_grigio = _in_grigio(wm)
    wm_resized = cv2.resize(wm_grigio, (n_colonne, n_righe), interpolation=cv2.INTER_NEAREST)
    _, wm_bin = cv2.threshold(wm_resized, 127, 255, cv2.THRESH_BINARY)
    return _in_float(wm_bin)


# ─────────────────────────────────────────────────────────────────────────────
# 1. LSB — Least Significant Bit
# ─────────────────────────────────────────────────────────────────────────────
def embed_lsb(
    host: NDArray[np.uint8],
    watermark: NDArray[np.uint8],
    alpha: float = 1.0,
) -> Tuple[NDArray[np.uint8], NDArray[np.float64]]:
    host_grigio = _in_grigio(host)
    alt, larg = host_grigio.shape
    n_righe, n_colonne = alt // DIM_BLOCCO, larg // DIM_BLOCCO

    # Otteniamo il watermark alla risoluzione a blocchi (es. 64x64)
    wm_float = _wm_a_griglia(watermark, n_righe, n_colonne)
    wm_bin = wm_float.astype(np.uint8)

    watermarked = host_grigio.copy()

    # Inseriamo UN SOLO BIT per blocco 8x8 (usiamo il pixel centrale del blocco)
    # Rimuove l'ingiusta ridondanza di 64 copie dello stesso bit
    for i in range(n_righe):
        for j in range(n_colonne):
            r = i * DIM_BLOCCO + 4  # Coordinata Y centrale del blocco
            c = j * DIM_BLOCCO + 4  # Coordinata X centrale del blocco
            watermarked[r, c] = (watermarked[r, c] & 0xFE) | wm_bin[i, j]

    chiave = np.zeros((1, 1), dtype=np.float64)
    return watermarked, chiave


def extract_lsb(
    image: NDArray[np.uint8],
    chiave: NDArray[np.float64],
    alpha: float = 1.0,
) -> NDArray[np.uint8]:
    img_grigio = _in_grigio(image)
    alt, larg = img_grigio.shape
    n_righe, n_colonne = alt // DIM_BLOCCO, larg // DIM_BLOCCO

    estratto = np.zeros((n_righe, n_colonne), dtype=np.uint8)
    
    # Leggiamo solo ed esclusivamente quel singolo pixel centrale
    for i in range(n_righe):
        for j in range(n_colonne):
            r = i * DIM_BLOCCO + 4
            c = j * DIM_BLOCCO + 4
            bit = img_grigio[r, c] & 1
            estratto[i, j] = bit * 255

    return estratto
# ─────────────────────────────────────────────────────────────────────────────
# 2. DCT — a blocchi 8x8, si modifica un coefficiente a media frequenza
# ─────────────────────────────────────────────────────────────────────────────
_DCT_POS = (4, 3)  # coefficiente a media frequenza (stile watermarking JPEG classico)


def embed_dct(
    host: NDArray[np.uint8],
    watermark: NDArray[np.uint8],
    alpha: float = 10.0,
) -> Tuple[NDArray[np.uint8], NDArray[np.float64]]:
    host_grigio = _in_grigio(host)
    alt, larg = host_grigio.shape
    n_righe, n_colonne = alt // DIM_BLOCCO, larg // DIM_BLOCCO

    wm_float = _wm_a_griglia(watermark, n_righe, n_colonne)
    img_float = host_grigio.astype(np.float64)

    watermarked = img_float.copy()
    coeff_originali = np.zeros((n_righe, n_colonne), dtype=np.float64)

    for i in range(n_righe):
        for j in range(n_colonne):
            r0, r1 = i * DIM_BLOCCO, (i + 1) * DIM_BLOCCO
            c0, c1 = j * DIM_BLOCCO, (j + 1) * DIM_BLOCCO
            blocco = img_float[r0:r1, c0:c1]
            dct_blocco = cv2.dct(blocco)
            coeff_originali[i, j] = dct_blocco[_DCT_POS]
            dct_blocco[_DCT_POS] += alpha * wm_float[i, j]
            watermarked[r0:r1, c0:c1] = cv2.idct(dct_blocco)

    chiave = np.stack([coeff_originali, wm_float], axis=-1)
    return _in_uint8(watermarked / 255.0), chiave


def extract_dct(
    image: NDArray[np.uint8],
    chiave: NDArray[np.float64],
    alpha: float = 10.0,
) -> NDArray[np.uint8]:
    coeff_originali = chiave[:, :, 0] if chiave.ndim == 3 else chiave
    img_grigio = _in_grigio(image).astype(np.float64)
    n_righe, n_colonne = coeff_originali.shape

    estratto = np.zeros((n_righe, n_colonne), dtype=np.float64)
    for i in range(n_righe):
        for j in range(n_colonne):
            r0, r1 = i * DIM_BLOCCO, (i + 1) * DIM_BLOCCO
            c0, c1 = j * DIM_BLOCCO, (j + 1) * DIM_BLOCCO
            blocco = img_grigio[r0:r1, c0:c1]
            dct_blocco = cv2.dct(blocco)
            estratto[i, j] = (dct_blocco[_DCT_POS] - coeff_originali[i, j]) / alpha

    estratto = np.clip(estratto, 0.0, 1.0)
    return _in_uint8(estratto)


# ─────────────────────────────────────────────────────────────────────────────
# 3. DWT — Haar 1 livello, implementata a mano (nessuna dipendenza esterna)
# ─────────────────────────────────────────────────────────────────────────────
def _haar_forward(img_float: NDArray[np.float64]):
    a = img_float[0::2, 0::2]
    b = img_float[0::2, 1::2]
    c = img_float[1::2, 0::2]
    d = img_float[1::2, 1::2]
    LL = (a + b + c + d) / 2.0
    HL = (a - b + c - d) / 2.0
    LH = (a + b - c - d) / 2.0
    HH = (a - b - c + d) / 2.0
    return LL, HL, LH, HH


def _haar_inverse(LL, HL, LH, HH, shape):
    a = (LL + HL + LH + HH) / 2.0
    b = (LL - HL + LH - HH) / 2.0
    c = (LL + HL - LH - HH) / 2.0
    d = (LL - HL - LH + HH) / 2.0
    out = np.zeros(shape, dtype=np.float64)
    out[0::2, 0::2] = a
    out[0::2, 1::2] = b
    out[1::2, 0::2] = c
    out[1::2, 1::2] = d
    return out


def embed_dwt(
    host: NDArray[np.uint8],
    watermark: NDArray[np.uint8],
    alpha: float = 10.0,
) -> Tuple[NDArray[np.uint8], NDArray[np.float64]]:
    host_grigio = _in_grigio(host)
    alt, larg = host_grigio.shape
    # Le dimensioni devono essere pari per la decimazione 2x2 dell'Haar
    alt_p, larg_p = alt - (alt % 2), larg - (larg % 2)
    img_float = host_grigio[:alt_p, :larg_p].astype(np.float64)

    LL, HL, LH, HH = _haar_forward(img_float)
    # Watermark inserito nella sub-banda HL (dettaglio orizzontale):
    # compromesso tipico invisibilità/robustezza migliore della LL, peggiore della HH
    wm_float = _wm_a_griglia(watermark, HL.shape[0], HL.shape[1])
    HL_originale = HL.copy()
    HL_mod = HL + alpha * wm_float

    ricostruita = _haar_inverse(LL, HL_mod, LH, HH, img_float.shape)
    watermarked = host_grigio.astype(np.float64).copy()
    watermarked[:alt_p, :larg_p] = ricostruita

    chiave = np.stack([HL_originale, wm_float], axis=-1)
    return _in_uint8(watermarked / 255.0), chiave


def extract_dwt(
    image: NDArray[np.uint8],
    chiave: NDArray[np.float64],
    alpha: float = 10.0,
) -> NDArray[np.uint8]:
    HL_originale = chiave[:, :, 0] if chiave.ndim == 3 else chiave
    n_righe, n_colonne = HL_originale.shape
    alt_p, larg_p = n_righe * 2, n_colonne * 2

    img_grigio = _in_grigio(image).astype(np.float64)
    img_float = img_grigio[:alt_p, :larg_p]

    _, HL, _, _ = _haar_forward(img_float)
    estratto = (HL - HL_originale) / alpha
    estratto = np.clip(estratto, 0.0, 1.0)
    return _in_uint8(estratto)


# ─────────────────────────────────────────────────────────────────────────────
# 4. SVD classica — whole image, metodo Liu & Tan (2002)
# ─────────────────────────────────────────────────────────────────────────────
def embed_svd_classica(
    host: NDArray[np.uint8],
    watermark: NDArray[np.uint8],
    alpha: float = 0.1,
) -> Tuple[NDArray[np.uint8], dict]:
    host_grigio = _in_grigio(host)
    alt, larg = host_grigio.shape

    wm_grigio = _in_grigio(watermark)
    wm_resized = cv2.resize(wm_grigio, (larg, alt), interpolation=cv2.INTER_AREA)
    _, wm_bin = cv2.threshold(wm_resized, 127, 255, cv2.THRESH_BINARY)

    host_float = host_grigio.astype(np.float64)
    wm_float = wm_bin.astype(np.float64)

    U, S, Vt = _robust_svd(host_float)
    Uw, Sw, Vtw = _robust_svd(wm_float)

    S_mod = S + alpha * Sw
    watermarked = U @ np.diag(S_mod) @ Vt

    # NOTA (limite noto e ben documentato in letteratura del metodo Liu & Tan):
    # per estrarre serve conservare l'intera base (Uw, Vtw) del watermark
    # originale, non solo i suoi valori singolari: è un limite intrinseco
    # del metodo classico rispetto all'approccio a blocchi del progetto.
    chiave = {"S_host": S, "Uw": Uw, "Vtw": Vtw, "shape": wm_bin.shape}
    return _in_uint8(watermarked / 255.0), chiave


def extract_svd_classica(
    image: NDArray[np.uint8],
    chiave: dict,
    alpha: float = 0.1,
) -> NDArray[np.uint8]:
    img_grigio = _in_grigio(image).astype(np.float64)
    _, S_att, _ = _robust_svd(img_grigio)

    S_host = chiave["S_host"]
    Uw, Vtw = chiave["Uw"], chiave["Vtw"]

    k = min(len(S_att), len(S_host))
    Sw_estratto = (S_att[:k] - S_host[:k]) / alpha
    Sw_estratto = np.clip(Sw_estratto, a_min=0.0, a_max=None)

    ricostruito = Uw[:, :k] @ np.diag(Sw_estratto) @ Vtw[:k, :]
    ricostruito = np.clip(ricostruito, 0.0, 255.0)
    _, bin_out = cv2.threshold(ricostruito.astype(np.uint8), 127, 255, cv2.THRESH_BINARY)
    return bin_out
