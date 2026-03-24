from __future__ import annotations
import numpy as np
from numpy.typing import NDArray
import cv2
from skimage.metrics import structural_similarity


def _in_grigio(img: NDArray[np.uint8]) -> NDArray[np.uint8]:
    # Converto in scala di grigi se necessario, altrimenti restituisco invariata
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img

def _allinea(riferimento: NDArray[np.uint8], destinazione: NDArray[np.uint8]) -> NDArray[np.uint8]:
    # Ridimensiono la destinazione per farla coincidere con il riferimento
    if riferimento.shape[:2] != destinazione.shape[:2]:
        return cv2.resize(
            destinazione,
            (riferimento.shape[1], riferimento.shape[0]),
            interpolation=cv2.INTER_AREA,
        )
    return destinazione


def calcola_psnr(
    originale: NDArray[np.uint8],
    modificata: NDArray[np.uint8],
) -> float: 
    orig = _in_grigio(originale).astype(np.float64)
    mod  = _in_grigio(_allinea(originale, modificata)).astype(np.float64)
    mse = np.mean((orig - mod) ** 2)
    if mse < 1e-12:
        return float("inf")
    return float(10.0 * np.log10(255.0 ** 2 / mse))


def calcola_ssim(
    originale: NDArray[np.uint8],
    modificata: NDArray[np.uint8],
) -> float: 
    orig = _in_grigio(originale)
    mod  = _in_grigio(_allinea(originale, modificata))
    return float(
        structural_similarity(orig, mod, data_range=255)
    )


def calcola_nc(
    watermark_originale: NDArray[np.uint8],
    watermark_estratto: NDArray[np.uint8],
) -> float: 
    orig = _in_grigio(watermark_originale).astype(np.float64).ravel()
    est  = _in_grigio(_allinea(watermark_originale, watermark_estratto)).astype(np.float64).ravel()
    denominatore = np.linalg.norm(orig) * np.linalg.norm(est)
    if denominatore < 1e-10:
        return 0.0
    return float(np.dot(orig, est) / denominatore)


def calcola_ber(
    watermark_originale: NDArray[np.uint8],
    watermark_estratto: NDArray[np.uint8],
    soglia: int = 128,
) -> float: 
    orig = _in_grigio(watermark_originale)
    est  = _in_grigio(_allinea(watermark_originale, watermark_estratto))
    orig_bin = (orig >= soglia).astype(np.uint8)
    est_bin  = (est  >= soglia).astype(np.uint8)
    return float(np.count_nonzero(orig_bin != est_bin) / orig_bin.size)