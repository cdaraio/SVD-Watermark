from __future__ import annotations
import numpy as np
from numpy.typing import NDArray
import cv2
 
def comprimi_jpeg(
    immagine: NDArray[np.uint8],
    quality: int = 50,
) -> NDArray[np.uint8]: 
    quality = int(np.clip(quality, 1, 100))
    parametri = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    successo, codificata = cv2.imencode(".jpg", immagine, parametri)
    if not successo:
        raise RuntimeError("Errore durante la codifica JPEG.")
    return cv2.imdecode(codificata, cv2.IMREAD_UNCHANGED)


def aggiungi_rumore_gaussiano(
    immagine: NDArray[np.uint8],
    media: float = 0.0,
    deviazione: float = 25.0,
) -> NDArray[np.uint8]: 
    generatore = np.random.default_rng()
    rumore = generatore.normal(media, deviazione, immagine.shape).astype(np.float64)
    # Evito valori fuori dal range 0-255
    immagine_rumorosa = np.clip(immagine.astype(np.float64) + rumore, 0.0, 255.0)
    return immagine_rumorosa.astype(np.uint8)


def aggiungi_rumore_salt_pepper(
    immagine: NDArray[np.uint8],
    densita: float = 0.05,
) -> NDArray[np.uint8]: 
    densita = float(np.clip(densita, 0.0, 1.0))
    risultato = immagine.copy()
    pixel = risultato.ravel()
    n_pixel = pixel.size
    n_per_tipo = int(n_pixel * densita / 2)
    generatore = np.random.default_rng()
    # Salt (pixel bianchi a 255)
    indici_salt = generatore.choice(n_pixel, size=n_per_tipo, replace=False)
    pixel[indici_salt] = 255
    # Pepper (pixel neri a 0).. escludo gli indici del salt per non sovrascrivere
    indici_rimanenti = np.setdiff1d(
        np.arange(n_pixel), indici_salt, assume_unique=True
    )
    n_pepper = min(n_per_tipo, indici_rimanenti.size)
    indici_pepper = generatore.choice(indici_rimanenti, size=n_pepper, replace=False)
    pixel[indici_pepper] = 0
    return risultato


def ritaglia(
    immagine: NDArray[np.uint8],
    frazione_ritaglio: float = 0.1,
) -> NDArray[np.uint8]: 
    frazione_ritaglio = float(np.clip(frazione_ritaglio, 0.0, 0.99))
    risultato = immagine.copy()
    altezza, larghezza = immagine.shape[:2]
    taglio_h = int(altezza * frazione_ritaglio)
    taglio_w = int(larghezza * frazione_ritaglio)
    risultato[:taglio_h, :taglio_w] = 0
    return risultato


def ruota(
    immagine: NDArray[np.uint8],
    angolo: float = 10.0,
) -> NDArray[np.uint8]: 
    # Usa BORDER_REFLECT_101 per evitare di creare bordi neri che alterano poi
    # i calcoli delle metriche NC e PSNR.
    altezza, larghezza = immagine.shape[:2]
    centro = (larghezza / 2.0, altezza / 2.0)
    matrice_rotazione = cv2.getRotationMatrix2D(centro, float(angolo), 1.0)
    return cv2.warpAffine(
        immagine,
        matrice_rotazione,
        (larghezza, altezza),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )