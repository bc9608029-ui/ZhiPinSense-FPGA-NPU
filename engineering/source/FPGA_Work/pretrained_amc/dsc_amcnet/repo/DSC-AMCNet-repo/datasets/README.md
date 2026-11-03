# Datasets

## RML2016.10a

**Source:** DeepSig Open Data  
**URL:** https://www.deepsig.ai/datasets  
**File:** `RML2016.10a_dict.dat` (pickled Python dict, ~55 MB)

### Contents

| Property | Value |
|---|---|
| Modulation classes | 11 (8PSK, AM-DSB, AM-SSB, BPSK, CPFSK, GFSK, PAM4, QAM16, QAM64, QPSK, WBFM) |
| SNR range | −20 to +18 dB (step 2 dB) |
| Samples per class/SNR | 1,000 |
| Total samples | 220,000 |
| Sample format | Complex IQ, 128 samples → shape (2, 128) float32 |

### Acquisition

1. Download `RML2016.10a_dict.dat` from [DeepSig](https://www.deepsig.ai/datasets).
2. Place it in this directory:
   ```
   datasets/RML2016.10a_dict.dat
   ```
3. Verify:
   ```bash
   python datasets/prepare_dataset.py \
       datasets/RML2016.10a_dict.dat \
       datasets/split_indices.npz
   ```
   Expected output:
   ```
   Total samples : 220,000
   Unique classes: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
   SNR range     : -20 to 18 dB
   Locked split (80/20 stratified, SEED = 42):
     Train : 176,000
     Test  :  44,000
   ```
   (Validation during training is carved from the train indices only;
   the locked test set is never used for model selection.)

## Dataset Split (split_indices.npz)

The train/val/test split is **locked** and archived on Zenodo:

> **DOI:** https://doi.org/10.5281/zenodo.20579317

Download `split_indices.npz` from Zenodo and place it in this directory.

The split was generated with a fixed random seed (seed = 42) and stratified
sampling to ensure equal class/SNR representation across splits. It must not
be regenerated — doing so will produce different accuracy numbers than those
reported in the paper.

### Why is the split locked?

Without a fixed split, two researchers training the same model may evaluate
on different samples, making results incomparable. Archiving the exact index
arrays on Zenodo allows anyone to independently verify all claims in the paper
using precisely the test set the authors used.

## RML2018.01a (cross-dataset generalization, paper Section X)

RML2018.01a (24 modulation classes, 1,024-sample windows) **is used** for
cross-dataset generalization: DSC-AMCNet-24 and LiteAMCNet-24 are trained
from scratch on it (no transfer learning), changing only the output layer
and, for DSC-AMCNet-24, adding a fourth MaxPool1d stage (paper Table IX:
+0.01 pp PTQ degradation at 24 classes; 48.28 KB Flash / 31.70 KB RAM).
Download it separately from DeepSig; note its much larger size (~20 GB).
