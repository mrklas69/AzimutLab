# KB — Hardware

Stroje, na kterých AzimutLab běží. Relevantní hlavně pro UC5 (trénink/inference modelu):
volba architektury, batch size a mixed precision se odvíjí od GPU. Dva stroje, sync jen
přes git (paměť `two-machines-git-sync`).

> Založeno Sez. 74 (2026-06-02), když UC5 trénink udělal z HW reálnou závislost.

## `mrkla` — HAL3000 (herní desktop, trénovací stroj)

Zdroj: CPU-Z report `StressTest/HAL3000.txt` (2026-06-02).

| Komponenta | Specifikace |
|------------|-------------|
| **GPU** | **NVIDIA GeForce RTX 5070** (ASUS), 12 GB GDDR7, 192bit; 6144 CUDA + 192 Tensor + 48 RT cores; Blackwell GB205, driver 32.0.15.9159 (12/2025) |
| **CPU** | AMD Ryzen 7 7700 — 8 jader / 16 vláken, Zen 4 (Raphael, 5 nm), boost ~5,3 GHz; AVX-512 vč. **BF16**/VNNI |
| **RAM** | 32 GB DDR5 (2× 16 GB Kingston/Samsung), ~6000 MT/s, dual-channel |
| **OS** | Windows 11 Home, build 26200 |
| **Monitor** | Samsung Odyssey G85SD 34,7" ultrawide 3440×1440 |

**Tohle je trénovací stroj.** 12 GB VRAM = pohodlně segmentační síť (U-Net + pretrained
encoder) s rozumným batch size; Tensor Cores → mixed-precision (BF16/FP16) trénink lokálně,
žádný cloud/Colab netřeba. Celý korpus 216 map se vejde do 32 GB RAM (rychlý dataset).

### ⚠ Past: Blackwell (sm_120) vyžaduje novou CUDA
RTX 5070 je architektura **Blackwell, compute capability sm_120** — velmi nová. Standardní
`pip install torch` může stáhnout build, který tuhle GPU nezná → runtime chyba
`CUDA error: no kernel image available for execution on the device`. Nutný **PyTorch build
proti CUDA 12.8+ (`cu128`)** s podporou Blackwell. **Přesnou verzi ověřit empiricky při
setupu, ne hádat** (verify-against-source): první test = `torch.cuda.is_available()` +
malý tensor na GPU, než se staví cokoli dalšího.

## `ntbhej` — HP EliteBook 855 G8 (notebook, editace/git)

Specifikace série (přesná konfigurace tohoto kusu TBD — doplnit, až bude po ruce):

| Komponenta | Specifikace (série) |
|------------|---------------------|
| **GPU** | **integrovaná AMD Radeon (Vega 6/7/8)** — bez CUDA, slabý FP výkon |
| **CPU** | AMD Ryzen 5000U (Cézanne, Zen 3, 15 W) — Ryzen 7 5850U / 5 5650U / 3 5450U dle konfigurace |
| **RAM** | DDR4-3200, typicky 16–32 GB |
| **Displej** | 15,6" FHD 1920×1080 IPS |

**NENÍ trénovací stroj.** Integrovaná Vega bez CUDA → PyTorch GPU akcelerace nedostupná
(ROCm Vega iGPU na Windows nepodporuje). Role `ntbhej`: editace kódu, git, lehká inference
na CPU max. **Veškerý trénink UC5 běží výhradně na `mrkla`.** Při přechodu mezi stroji
(paměť `two-machines-git-sync`) tedy natrénované váhy putují přes git/úložiště, ne že by se
přetrénovávaly.

## Důsledky pro UC5
- Trénink **jen na `mrkla`** (RTX 5070). Inference může běžet i na CPU (`ntbhej`), pomaleji.
- **Mixed precision (BF16)** zapnout — Tensor Cores na Blackwell jsou na to stavěné.
- VRAM 12 GB je strop pro batch size × rozlišení dlaždice — ladit, ne přestřelit.
- Precedent z Pic2Omapu: U-Net resnet34 area segmentation (mIoU 0,666, viz `tools-models.md`)
  — sourozenecký kód, kandidát na výchozí architekturu runnability modelu.

## Zdroje
- CPU-Z report `mrkla`: `StressTest/HAL3000.txt`
- [HP EliteBook 855 G8 spec sheet (HP)](https://www.hp.com/content/dam/sites/garage-press/press/press-kits/2021/ces-2021/hp_elitebook_855_g8_media_spec_sheet.pdf)
- [HP EliteBook 855 G8 — LaptopMedia](https://laptopmedia.com/series/hp-elitebook-855-g8/)
