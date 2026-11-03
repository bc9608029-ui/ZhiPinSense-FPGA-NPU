# RML24 TF32 24-class network mapping audit

Audit token: `M29-RML24-FIX10CLASS24-TF32-NETWORK-AUDIT`

| field | value |
|---|---|
| network name | `model_24class` |
| model name | `rml24_adamrv11_tf32` |
| icraft | `v3.39.0` (xir `3.39.0.0`) |
| framework | `ONNX` `opset17` |
| ai target | `@zhuget(330)` |
| params_bytes | 1423004 |
| params_md5 | `e48e59f5a2da56a99875ade883d508da` |
| json SHA256 | `8d00a1c31835611f18064389e5b9ecab755afefa5bacd78a983119757e65fa37` |
| raw SHA256 | `f8366a109576ea53c9b3ddfd2e7b690590515ff3dfb33c6af7cf6ccafcdb392e` |
| source checkpoint SHA256 | `96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d` |
| source ONNX SHA256 | `976618a131e75f23bd46e04e71a114cbbea245d6afdd4c7ea7fa008e0ce9ed51` |

## Op inventory

- Input: 1, HardOp: 118, Output: 1 (total 120)
- compile target: `{'@hostt': 2, '@zhuget(330)': 118}`
- NPU-resident ops: **118**, host ops: **2**
- HardOp node types: `{'icraft::xir::CastNode': 3, 'icraft::xir::ReshapeNode': 37, 'icraft::xir::TransposeNode': 34, 'icraft::xir::Conv2dNode': 28, 'icraft::xir::AddNode': 12, 'icraft::xir::MeanNode': 1, 'icraft::xir::MatmulNode': 2, 'icraft::xir::PruneAxisNode': 1}`

## Network I/O

- input  `[1, 2, 1024]` fp32
- output `[1, 24]` fp32

## Dtype census (recomputed from JSON)

- activation values: 119 unique
  - quantized storage `{'@tf(32)': 117}`, expressed `{'@fp(32)': 117}`, plain `{'@fp(32)': 2}`
- params: 177
  - quantized storage `{'@tf(32)': 59}`, expressed `{'@fp(32)': 59}`, plain `{'@uint(64)': 118}`

## Deployability

- **DEPLOYABLE_FULL_NETWORK_TF32** (int8 tensors: 0, bf16 tensors: 0)

