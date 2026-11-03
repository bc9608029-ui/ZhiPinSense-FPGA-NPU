# DSC-AMCNet: Deployment-Guided Automatic Modulation Classification on Bare-Metal MCU-Class IoT Devices

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21167587.svg)](https://doi.org/10.5281/zenodo.21167587)

Official code and artifacts for the paper:

> **"DSC-AMCNet: Deployment-Guided Automatic Modulation Classification on Bare-Metal MCU-Class IoT Devices"**  
> *IEEE Internet of Things Journal (under review), 2026*

---

## Overview

DSC-AMCNet is a lightweight neural network for **Automatic Modulation Classification (AMC)** designed for deployment on bare-metal embedded hardware. This repository provides everything needed to reproduce all experimental results reported in the paper, including:

- Model training and evaluation (RML2016.10a)
- Post-Training Quantization (PTQ) to INT8 with X-CUBE-AI-compatible backend
- Deployment on STM32H723ZG (ARM Cortex-M7, 544 MHz) with DWT cycle-accurate latency measurement
- Four-tier over-the-air (OTA) validation (HackRF One TX → RX loopback via SMA attenuator; live FM/AM broadcast reception)

---

## Key Results (Locked, Silicon-Measured)

| Model | Latency (ms) | Flash (KB) | RAM (KB) | INT8 Acc. @+10 dB | PTQ Degr. |
|---|---|---|---|---|---|
| DSC-AMCNet INT8 | **1.183** | **51.26** | **12.09** | **86.92%** | **0.09 pp** |
| ULCNN-simplified INT8 | 2.104 | 49.25 | 36.78 | 87.55% | 1.95 pp |
| **DSC vs ULCNN** | **1.78× faster** | — | **−24.69 KB** | within ±1.4 pp Wilson CI | **22× lower** |

> All values measured on physical hardware (DWT cycle counters, 544 MHz, ICache + DCache). Energy: **0.091 mJ**/inference (955.1 acc/mJ). No extrapolation.

---

## Repository Structure

```
DSC-AMCNet/
├── models/
│   ├── dsc_amcnet.py           # Model architecture (PyTorch)
│   ├── train.py                # Training script (RML2016.10a)
│   └── checkpoints/
│       └── README.md           # Download links (Zenodo)
├── datasets/
│   ├── prepare_dataset.py      # Dataset loading + locked split
│   └── README.md               # Dataset acquisition instructions
├── quantization/
│   ├── ptq_quantize.py         # PTQ pipeline (fbgemm → ONNX → X-CUBE-AI)
│   ├── validate_backend.py     # qnnpack vs fbgemm validation
│   └── qat_experiment.py       # QAT experiment (documented failure)
├── stm32_deployment/
│   ├── firmware/
│   │   ├── inference_main.c    # STM32 inference loop
│   │   └── dwt_measure.c       # DWT cycle-accurate timing
│   └── README.md               # STM32CubeIDE setup instructions
├── hardware_characterization/
│   ├── measure_latency.py      # Serial latency logger
│   └── analyze_flash_ram.py    # Flash/RAM parser (ST Edge AI Core)
├── ota_collection/
│   └── collect_ota.py          # OTA capture + noise-floor-referenced SNR
├── supplementary/
│   ├── appendix_a_architecture.md   # Layer-by-layer specification
│   ├── appendix_b_per_modulation.md # Per-class accuracy breakdown
│   └── appendix_c_qat_failure.md    # QAT failure analysis
├── requirements.txt
├── environment.yml
└── README.md
```

---

## Quick Start

### 1. Environment Setup

```bash
conda env create -f environment.yml
conda activate dsc-amcnet
```

Or with pip:
```bash
pip install -r requirements.txt
```

### 2. Dataset

Download RML2016.10a from [DeepSig](https://www.deepsig.ai/datasets) and place the file at:
```
datasets/RML2016.10a_dict.dat
```

See `datasets/README.md` for full instructions.

### 3. Train DSC-AMCNet

```bash
python models/train.py \
    --data datasets/RML2016.10a_dict.dat \
    --split datasets/split_indices.npz \
    --epochs 100 \
    --output models/checkpoints/dscamcnet_best.pt
```

Expected result: **87.01% FP32 accuracy** at +10 dB (seed-to-seed variance ±0.23 pp), matching Table II of the paper.

### 4. Quantize to INT8

```bash
python quantization/ptq_quantize.py \
    --checkpoint models/checkpoints/dscamcnet_best.pt \
    --data datasets/RML2016.10a_dict.dat \
    --split datasets/split_indices.npz \
    --output quantization/outputs/dscamcnet_int8.onnx
```

> **Critical:** Uses `fbgemm` backend (signed INT8, X-CUBE-AI compatible). See `quantization/validate_backend.py` for why `qnnpack` must NOT be used.

### 5. STM32 Deployment

See `stm32_deployment/README.md` for:
- X-CUBE-AI model import workflow
- STM32CubeIDE project configuration
- Flashing and running DWT latency measurements

### 6. OTA Evaluation

```bash
python ota_collection/collect_ota.py \
    --freq 433.92e6 \
    --sample_rate 2e6 \
    --n_windows 5000 \
    --output ota_results.npz
```

---

## Reproducing Paper Claims

| Paper Claim | Script | Expected Output |
|---|---|---|
| FP32 accuracy 87.01% @ +10 dB | `models/train.py` | ≥ 86.5% (seed variance ±0.23 pp) |
| INT8 Flash 51.26 KB, RAM 12.09 KB | `stm32_deployment/` + ST Edge AI Core | Analyze report |
| INT8 latency 1.183 ms @ 544 MHz | `hardware_characterization/measure_latency.py` | Serial log |
| Tier-3 OTA accuracy 82.76% | `ota_collection/collect_ota.py` | `.npz` results file |
| PTQ degradation 0.09 pp @ +10 dB | `quantization/ptq_quantize.py` | Eval log |

---

## Pre-trained Weights

Model checkpoints and dataset split indices are archived on Zenodo:

> **DOI:** [10.5281/zenodo.21167587](https://doi.org/10.5281/zenodo.21167587)

Download and place files as described in `models/checkpoints/README.md`.

---

## Environment

| Component | Version |
|---|---|
| Python | 3.10+ (developed on 3.14) |
| PyTorch | 2.x |
| ONNX | 1.26.0 |
| STM32CubeIDE | 1.15.x |
| X-CUBE-AI / ST Edge AI Core | 10.2.0 / 2.2.0 |
| Hardware | STM32H723ZG Nucleo, HackRF One, RTL-SDR Blog V3 |

---

## Citation

If you use this work, please cite:

```bibtex
@article{dscamcnet2026,
  title   = {{DSC-AMCNet}: Deployment-Guided Automatic Modulation
             Classification on Bare-Metal {MCU}-Class {IoT} Devices},
  author  = {Mishra, Suryaprakash},
  journal = {IEEE Internet of Things Journal},
  year    = {2026},
  note    = {Under review}
}
```

---

## License

This project is released under the [MIT License](LICENSE).
