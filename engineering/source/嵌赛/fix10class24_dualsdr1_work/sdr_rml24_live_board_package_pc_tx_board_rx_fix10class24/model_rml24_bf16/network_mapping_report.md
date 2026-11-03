# RML24 BF16 24-class network mapping audit

Audit token: `M29-RML24-FIX10CLASS24-BF16-NETWORK-AUDIT`

| field | value |
|---|---|
| network name | `model_24class` |
| model name | `rml24_adamrv11_bf16` |
| icraft | `v3.39.0` (xir `3.39.0.0`) |
| framework | `ONNX` `opset17` |
| ai target | `@zhuget(330)` |
| params_bytes | 778732 |
| params_md5 | `0c9b60b82ea1f634469b598db45738fb` |
| json SHA256 | `28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42` |
| raw SHA256 | `c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151` |

## Op inventory

- Input: 1, HardOp: 122, Output: 1 (total 124)
- compile target: `{'@hostt': 2, '@zhuget(330)': 122}`
- NPU-resident ops: **122**, host ops: **2**
- HardOp node types: `{'icraft::xir::CastNode': 6, 'icraft::xir::ReshapeNode': 39, 'icraft::xir::TransposeNode': 33, 'icraft::xir::Conv2dNode': 28, 'icraft::xir::AddNode': 12, 'icraft::xir::MeanNode': 1, 'icraft::xir::MatmulNode': 2, 'icraft::xir::PruneAxisNode': 1}`

## Network I/O

- input  `[1, 2, 1024]` fp32
- output `[1, 24]` fp32

## Dtype census (recomputed from JSON)

- activation values: 123 unique
  - quantized storage `{'@tf(32)': 8, '@bf(16)': 113}`, expressed `{'@fp(32)': 121}`, plain `{'@fp(32)': 2}`
- params: 181
  - quantized storage `{'@bf(16)': 30}`, expressed `{'@fp(32)': 30}`, plain `{'@uint(64)': 122, '@fp(16)': 29}`

## Deployability

- **DEPLOYABLE_FULL_NETWORK_BF16** (int8 tensors: 0)

