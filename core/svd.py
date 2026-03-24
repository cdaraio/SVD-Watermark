from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
import cv2
from typing import Tuple

# Dimensione del blocco in pixel 8x8
DIM_BLOCCO: int = 8

def _in_float(img: NDArray[np.uint8]) -> NDArray[np.float64]:
    # Scala i pixel dell'immagine dal range 0-255 al range 0.0-1.0
    return img.astype(np.float64) / 255.0

def _in_uint8(img: NDArray[np.float64]) -> NDArray[np.uint8]:
    # Riporta i pixel dal range 0.0-1.0 al formato immagine standard (0-255)
    return np.clip(img * 255.0, 0.0, 255.0).astype(np.uint8)

def _in_grigio(img: NDArray) -> NDArray[np.uint8]:
    # Converte l'immagine a scala di grigi se ha 3 canali (colori)
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img.copy()

#api

def embed_watermark(
    host: NDArray[np.uint8],
    watermark: NDArray[np.uint8],
    alpha: float = 0.1,
) -> Tuple[NDArray[np.uint8], NDArray[np.float64]]: 
    # Modifica il valore singolare dominante (S[0]) di ogni blocco 8x8
    host_grigio = _in_grigio(host)
    wm_grigio   = _in_grigio(watermark)
    alt, larg = host_grigio.shape
    n_righe = alt // DIM_BLOCCO
    n_colonne = larg // DIM_BLOCCO
    # Ridimensiono il watermark in modo che ogni suo singolo pixel 
    # vada a finire dentro un intero blocco 8x8 dell'immagine 
    wm_ridimensionato = cv2.resize(wm_grigio, (n_colonne, n_righe), interpolation=cv2.INTER_AREA)
    wm_float = _in_float(wm_ridimensionato)
    img_float = _in_float(host_grigio)
    immagine_watermarked = img_float.copy()
    # Matrice per salvare i valori singolari originali(key)
    original_svs: NDArray[np.float64] = np.zeros((n_righe, n_colonne), dtype=np.float64)
    for i in range(n_righe):
        for j in range(n_colonne):
            # Calcolo  coordinate del blocco 8x8 corrente
            r0, r1 = i * DIM_BLOCCO, (i + 1) * DIM_BLOCCO
            c0, c1 = j * DIM_BLOCCO, (j + 1) * DIM_BLOCCO
            blocco = img_float[r0:r1, c0:c1]
            # Decomposizione SVD del blocco
            U, S, Vt = np.linalg.svd(blocco, full_matrices=False)
            # Salvo il valore singolare dominante originale
            original_svs[i, j] = S[0]
            S_modificato = S.copy()
            # Inserisco l'informazione: sommo il pixel del watermark moltiplicato per alpha
            S_modificato[0] += alpha * wm_float[i, j]
            # Ricostruisco il blocco modificato moltiplicando U * Sigma * Vt
            immagine_watermarked[r0:r1, c0:c1] = U @ np.diag(S_modificato) @ Vt
    return _in_uint8(immagine_watermarked), original_svs


def extract_watermark(
    image: NDArray[np.uint8],
    original_svs: NDArray[np.float64],
    alpha: float = 0.1,
) -> NDArray[np.uint8]:
    # Estrazione: serve l'immagine (anche attaccata) e la chiave
    img_grigio = _in_grigio(image)
    img_float = _in_float(img_grigio)
    n_righe, n_colonne = original_svs.shape
    watermark_estratto: NDArray[np.float64] = np.zeros((n_righe, n_colonne), dtype=np.float64)
    for i in range(n_righe):
        for j in range(n_colonne):
            r0, r1 = i * DIM_BLOCCO, (i + 1) * DIM_BLOCCO
            c0, c1 = j * DIM_BLOCCO, (j + 1) * DIM_BLOCCO
            blocco = img_float[r0:r1, c0:c1]
            # SVD sul blocco(attaccato)
            _, S, _ = np.linalg.svd(blocco, full_matrices=False)
            # Formula inversa per stimare il pixel del watermark
            watermark_estratto[i, j] = (S[0] - original_svs[i, j]) / alpha
    # Possibili valori anomali o negativi del risultato,normalizzo tutto tra 0 e 1, 
    # in modo da poterlo visualizzare come una normale immagine
    val_min = watermark_estratto.min()
    val_max = watermark_estratto.max()
    if (val_max - val_min) > 1e-10:
        watermark_estratto = (watermark_estratto - val_min) / (val_max - val_min)
    else:
        watermark_estratto[:] = 0.0
    return _in_uint8(watermark_estratto)