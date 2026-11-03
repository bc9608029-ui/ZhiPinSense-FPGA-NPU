# RML23-AMSSB-MERGED — board candidate package (M29 Phase F4)

Deployment-layer label merge for the RML2018 24-class NPU model on FMQL30TAI +
ZG330 (iCraft v3.39.0, target `@zhuget(330)`).

**What this is.** The 24-class FP32 model is fine, but under vendor INT8 the
AM-SSB-SC sub-class collapses systematically.  Rather than retrain, this package
merges the two AM-SSB sub-classes *in software, at the deployment layer*:

```
NPU -> float logits[24] (raw, unchanged)
    -> save raw logits
    -> merged[17] = logaddexp(logit_AM_SSB_SC, logit_AM_SSB_WC)   # log(exp(SC)+exp(WC))
    -> 23-class argmax -> "AM-SSB" -> UI
```

- NPU still emits **raw 24-dim logits**; the 24-dim index, input preprocessing,
  and model weights are all **unchanged**.
- Software post-processing emits **23 classes**.  UI shows `RML23-AMSSB-MERGED`
  and the label `AM-SSB` (never `AM-SSB-SC` / `AM-SSB-WC`).
- No SC/WC binary expert is trained or run in this package (`expert_enabled=false`,
  `expert_result=NOT_RUN`).  No fake rule-based SC/WC split.
- Model is loaded **once** by the existing driver — no per-frame reopen, no
  added frame latency, no new NPU operators.
- **Bitstream unchanged** — this is a software + model-only deployment.

## Package layout

```
rml23_merged.hpp                 header-only 23-class merge (namespace rml23)
src/rml23_merged_main.cpp        integration example: file -> merge -> JSONL
rml23_merged_test.cpp            self-test: 40 assertions + cross-language + stability
test_data/*.bin                  cross-language reference data (expA, 1536 frames)
model/model_24class_ZG.json      frozen NPU model (expA_bf16_head)
model/model_24class_ZG.raw       frozen NPU weights (expA_bf16_head)
contract/rml23_merged_contract.py  frozen 23-class contract (pure stdlib)
contract/rml23_merged_contract.json
scripts/build_board.sh           build (from source) + self-test ON the board
scripts/verify_package.sh        fail-closed manifest + model + contract identity
scripts/verify_rml23_contract.py recompute frozen contract SHAs
scripts/start_rml23.sh           run the merge chain over a logits stream
scripts/stop_rml23.sh            stop the chain (pidfile)
scripts/check_ui_result.sh       UI/result log validation
scripts/test_1000_frames.sh      1000-frame board test (run + validate)
scripts/test_10000_frames.sh     10000-frame stability test (run + determinism)
scripts/rollback.sh              restore previous model/ (no flash/bitstream touch)
SHA256SUMS.txt                   SHA256 manifest over every content file
```

## Frozen identity (do not modify)

| artifact | SHA256 |
|---|---|
| `model/model_24class_ZG.json` | `d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d` |
| `model/model_24class_ZG.raw`  | `2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba` |
| `params_md5`                  | `7966a4829fc713b2e8ea6c04168be263` |
| 23-class label order SHA256   | `15072cd29538b08bc53f4e59237994297d71d5eb44d499413f9bb08929459c88` |
| merged contract SHA256        | `f9f7f3812ace1ec523c810408a31c6fc12b979d7d62900b90924cabf08bebb1e` |
| source 24-class label SHA256  | `3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549` |

## Upload / verify / run / rollback

```sh
# 1. upload (scp/rsync the tarball to the board, then)
mkdir -p /opt/sdr/rml23 && tar -xzf sdr_rml23_amssb_merged_board_package.tar.gz -C /opt/sdr/rml23
cd /opt/sdr/rml23

# 2. verify (fail-closed: manifest + model SHA + contract SHA)
./scripts/verify_package.sh

# 3. build the merge post-processor from source ON THE BOARD (aarch64)
./scripts/build_board.sh

# 4. run over a captured 24-dim logits stream (e.g. 1000-frame test)
./scripts/test_1000_frames.sh /data/npu_logits_1000.f32

# 5. 10000-frame stability + determinism test
./scripts/test_10000_frames.sh /data/npu_logits_10000.f32

# 6. rollback (restores model.prev/, never touches flash/bitstream)
./scripts/rollback.sh
```

### Board runtime dependencies (NOT shipped)

The package ships **no prebuilt binary** and **no vendor runtime libraries**.
The board executable is built from source by `scripts/build_board.sh`.  The
existing board already provides:

- the **iCraft NPU runtime** (loads `model_24class_ZG.json` / `.raw`), and
- the **existing 24-class capture driver** that produces per-frame raw 24-dim
  float32 logits.

The merge post-processor (`bin/rml23_merged_main`) is pure C++ (C++17, header
only, no external libs).  The single integration point is the call to
`rml23::merge_predict(logits24, &result)` — see `src/rml23_merged_main.cpp`.

### Architecture guard

`scripts/build_board.sh` refuses to build with a bare `g++` on a non-`aarch64`
host, so an x86/WSL binary can never be produced or mistaken for a board binary.
Set `CXX=<aarch64-linux-g++>` to cross-compile if your board toolchain is on the
host.  The package itself contains **no Windows / x86 / WSL binaries**.

## Offline validation (already performed on the host, recorded for audit)

- Host C++ self-test: 40/40 assertions; cross-language vs Python on 1536 real
  expA frames: merged top-1 mismatch = 0, raw top-1 mismatch = 0, max abs
  logit diff = 9.537e-7.
- 1000-frame and 10000-frame stability: 0 invalid / non-finite frames.
- Selection evidence: `expA_bf16_head` is the only candidate passing all 8
  promotion gates vs FP32 on the fixed 1536 validation subset (see
  `docs/M29_PHASE_F2_RML23_MERGED_EVALUATION.md`).
