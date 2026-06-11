import numpy as np
import cv2

# Crea una matrice 64x64 con un pattern a scacchiera (perfettamente binario)
logo = np.zeros((64, 64), dtype=np.uint8)
logo[::2, ::2] = 255
logo[1::2, 1::2] = 255

# Salva come BMP (formato non compresso, bit puri)
cv2.imwrite("watermark_test_binario.bmp", logo)
print("File 'watermark_test_binario.bmp' creato.")