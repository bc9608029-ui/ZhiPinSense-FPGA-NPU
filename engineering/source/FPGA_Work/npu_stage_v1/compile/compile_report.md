# iCraft 3.39 compile record (section 二)

## Tool & inputs

| Item | Value |
|---|---|
| Compiler | `C:/Icraft/CLI v3.39.0/bin/icraft.exe` (v3.39.0, confirmed in parsed JSON) |
| Config | `compile_config.toml` |
| Source model | `models/time_power_phase_npu_partition_opset17.onnx` (294,583 B) |
| Source SHA-256 | `2e50146503bbe3df564b244515e0ed74d23d6f06f44e3cd715194a3bdd50051d` |
| Calibration | `calibration/cal_data/` (168 samples) + `calibration/forward_list.txt` |
| Target | ZG330 (`zhuge` / `ZHUGE`, ai_target `@zhuget(330)`) |

## Pipeline result (all 5 stages exit 0)

| Stage | Output json | Output raw | Notes |
|---|---|---|---|
| parse | `rfnet_npu_parsed.json` (74,284 B) | `.raw` (284,984 B) | 104 ops; ONNX opset 17; inputs FP32 [1,2,1024]+[1,3,1024], output [1,8] |
| optimize | `rfnet_npu_optimized.json` (54,597 B) | `.raw` (284,984 B) | 71 ops; BN folded into convs; one harmless AvgPool `count_include_pad` flag (pad=0 → no-op) |
| quantize | `rfnet_npu_quantized.json` (124,060 B) | `.raw` (73,364 B) | 77 ops; per-channel KLD, symmetric; Cast quantize inserted |
| adapt | `rfnet_npu_adapted.json` (225,064 B) | `.raw` (2,205,672 B) | 159 ops; 157 @zhuget(330) + 2 @hostt (IO) |
| generate | `rfnet_npu_ZG.json` (140,873 B) | `rfnet_npu_ZG.raw` (2,507,348 B) | 87 ops (85 HardOp + Input + Output); final board artifact |

## SHA-256 of final artifact

| File | Size | SHA-256 |
|---|---|---|
| `rfnet_npu_ZG.json` | 140,873 B | `ad57fc0b4a9ec5ae6e8cd2d2c2c0c91f81ef4e5fc7898447b322dc00c349a2e4` |
| `rfnet_npu_ZG.raw` | 2,507,348 B | `c48979b3ab1bc62fa2efcfb07202ee640513f424244d15d089c89a6d2260b42a` |
| params_md5 (json) | — | `9c5bb6606fdd5600940bd5d9f0d0ba92` |

## Final compiled contract (the gate)

| Item | Value |
|---|---|
| Input 0 | `iq` FP32 `[1,2,1024]` layout `**C` (channel-first / NCL) |
| Input 1 | `physical_features` FP32 `[1,3,1024]` layout `**C` |
| Input byte sizes | 8,192 B + 12,288 B |
| Internal quantize scale | iq `0.0071911365`, physical `0.011158751` (per-channel, symmetric, zero-point empty) |
| Compute storage | `@sint(8)` (int8 quant took effect) |
| Output | `logits` FP32 `[1,8]` (32 B) |
| Op mapping | 85 @zhuget(330) + 2 @hostt (Input + Output); **no HostBackend** |

## Non-fatal warnings (recorded, not waived)

1. `AvgPool (op 45) count_include_pad=False -> True` — verified harmless: the pool is
   global (pool_width=128, all pad_* = 0), so the divisor is 128 either way. No math change.
2. `no_imagemake not supported under zhuge target` — no-op for non-image input.
3. `ConcatNormratio: change input normratio to same value` — standard quantizer normalization.
4. `LoadingNvfuserLibrary` (WinError 126) — torch nvfuser DLL absent on host; irrelevant to NPU codegen.

No operator was deleted/replaced, no HostBackend fallback was introduced, no input shape,
quantization rule, or model math was changed to make the compile pass.
