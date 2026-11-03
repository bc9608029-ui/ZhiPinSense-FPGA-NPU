# Pre-trained Checkpoints

Pre-trained model weights and the locked dataset split are archived on Zenodo
to ensure long-term, citable availability independent of this repository.

## Download

**Zenodo Archive:** https://doi.org/10.5281/zenodo.20579317

Download and place files as follows:

```
models/checkpoints/
├── dscamcnet_best.pt          ← DSC-AMCNet FP32 weights (4,961 params)
├── dscamcnet_int8.onnx        ← INT8 ONNX (QDQ, signed INT8; opset 13, IR 8)
└── ulcnn_fp32_fixed.onnx      ← ULCNN-simplified baseline (FP32 ONNX)
datasets/
└── split_indices.npz          ← Locked 80/20 train/test split
```

## Integrity Verification

After downloading, verify SHA-256 checksums:

| File | SHA-256 |
|------|---------|
| `dscamcnet_best.pt` | `4827d8dc549866390fe22914c6ba3f6be03e4330dc9e0f0aa750013e8160a06e` |
| `dscamcnet_int8.onnx` | `6d3520a3081aa07d47713b4253d30a09f07e754fe8db0e5ddc9e7327ce5e78dd` |
| `ulcnn_fp32_fixed.onnx` | `7c4936039fb0df17e7fa15322a9d5c4cd81847cea5fa7b54a39bd79e5b22a8e9` |
| `split_indices.npz` | `69c8ed46e301f374f0beecb3919495a55e7fff73bebbad7e156a7f97d2e8d61b` |

Verify on Linux/macOS:
```bash
sha256sum models/checkpoints/dscamcnet_best.pt
sha256sum datasets/split_indices.npz
```

Verify on Windows (PowerShell):
```powershell
Get-FileHash models\checkpoints\dscamcnet_best.pt -Algorithm SHA256
Get-FileHash datasets\split_indices.npz -Algorithm SHA256
```

## Notes

- The `split_indices.npz` is **locked** — it defines the exact 80/20 train/test partition
  used in all paper experiments. Using a different split will produce different accuracy
  numbers. This is expected.
- The INT8 ONNX carries signed INT8 (QDQ; zero-point 0). Unsigned INT8
  (qnnpack-style, zero-point 128) is incompatible with X-CUBE-AI and fails
  silently on device. See `quantization/validate_backend.py`.
