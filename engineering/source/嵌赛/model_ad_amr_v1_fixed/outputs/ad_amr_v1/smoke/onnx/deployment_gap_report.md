# AD-AMR V1 — Deployment Gap Report

The AD-AMR Net (ICC 2024) is an independent research line.  Its denoising
front-end (WaveUNet + ECA + adaptive soft-thresholding) was designed for
classification accuracy, not for the frozen 8-operator NPU policy of the
V2/V3.3 track.  This report documents that gap honestly.

## Exported graph
- ONNX opset: 17
- checker: passed
- operators: {"Abs": 4, "Add": 4, "Concat": 4, "Constant": 52, "Conv": 34, "Gemm": 2, "Mul": 16, "ReduceMean": 13, "Relu": 22, "Resize": 4, "Sigmoid": 12, "Sign": 4, "Squeeze": 24, "Sub": 4, "Unsqueeze": 24}
- parameter count: 288236
- neural MACs: 32525014

## Gap vs frozen NPU whitelist
Whitelist: ["Add", "BatchNormalization", "Concat", "Conv", "Gemm", "Mul", "ReduceMean", "Relu"]
Operators outside the whitelist: ["Abs", "Constant", "Resize", "Sigmoid", "Sign", "Squeeze", "Sub", "Unsqueeze"]

- `Abs`: adaptive soft-thresholding |x| and the per-channel threshold magnitude.
- `Constant`: see the traced graph.
- `Resize`: WaveUNet nearest-neighbour x2 upsampling in the ADM decoder.
- `Sigmoid`: ECA channel-attention gating (GAP -> Conv1d -> Sigmoid -> multiply).
- `Sign`: soft-thresholding sign(x) * relu(|x| - lambda).
- `Squeeze`: see the traced graph.
- `Sub`: see the traced graph.
- `Unsqueeze`: see the traced graph.

## Conclusion
Deployment to the ZG330 NPU under the current 8-op policy is NOT possible
without re-architecting the denoiser (e.g. replacing soft-thresholding with
a policy-approved op and nearest upsample with a transposed-conv variant,
then re-validating).  No NPU deployment is claimed for AD-AMR V1.
