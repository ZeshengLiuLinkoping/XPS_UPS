---
title: UPS / XPS IBW Processor
emoji: 📊
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: "4.0.0"
app_file: app.py
pinned: false
license: mit
# 使用 Python 3.11 避免 3.13 中移除 audioop 导致的 Gradio/pydub 报错
python_version: "3.11"
---

# UPS / XPS IBW Processor

Process **IGOR .ibw** (binary wave) files from UPS/XPS: normalize intensity, preview spectra, and export CSV + PNG. Output filenames include **auto-detected orbital/range** (e.g. C1s, O1s, S2p, BE284-292).

## Features

- **Upload** multiple `.ibw` files
- **Preview**: overlay all spectra or one figure per file; **SECO / work function φ = 21.22 − SECO** on plot and in status; optional zoom panels with **custom Zoom A/B range** when spectrum starts from 20 eV
- **CSV export**: separate CSV per file, or one merged CSV (each file = 3 columns, empty column between files)
- **PNG export**: optional; filenames include orbital/range tag
- **Orbital auto-ID**: 40+ common XPS orbitals (C1s, O1s, N1s, S2p, F1s, Ti2p, Fe2p, …) from scan range

## How to use

1. Upload one or more `.ibw` files.
2. Choose **Plot mode** (overlay / separate) and **CSV export** (separate per file / merged horizontal).
3. Optionally enable **Export PNG** and **Zoom panels** (zoom only applies when data starts from 20 eV).
4. Click **Preview** to see the plot.
5. Click **Export CSV + PNG → ZIP** to generate a ZIP with all CSV (and PNG if enabled); download from the file box.

## Local run

```bash
pip install -r requirements.txt
python app.py
```

## License

MIT
