"""ImageNet normalizace — SSoT pro všechny tři reconstructory (audit D4/B3, Sez. 158).

Dřív byly `MEAN`/`STD` duplikované 6× (3× `*/dataset.py` jako `_IMAGENET_MEAN/_STD`, 3× `*/eval_real.py`
jako lokální `MEAN`/`STD`) — to je train/serve skew riziko: změna normalizace v tréninku by se TIŠE
nepropsala do `eval_real` na vrcholové metrice. Teď jeden zdroj.

Hodnoty = standardní ImageNet statistiky (smp.Unet `encoder_weights="imagenet"`), RGB, vstup škálovaný [0,1].
"""
import numpy as np

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
