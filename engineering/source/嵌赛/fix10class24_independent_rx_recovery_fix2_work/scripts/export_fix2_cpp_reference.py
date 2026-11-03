#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""export_fix2_cpp_reference.py -- 导出 C++ 交叉核验参考（A线 fix2）。

纯离线。对 24 份真实 v2 双 SDR 捕获：读原始 int16 -> 定位前导（暴力，与
reproduce_fix2_diagnosis 一致）-> 切片 59904 复样本 -> 落盘**精确切片 int16 字节**
（无重量化）-> 计算 fix2 估计 + v2 恢复张量 SHA。C++ host 测试读切片 burst，复现
estimate_public_reference + recover_model_input，逐帧核验 (cfo,τ,a,b,residual_rel) 与
恢复张量 SHA（除末位 ULP 浮点差异外逐字节一致）。

为什么切片不重量化：deinterleave(slice(inter[2*off:...])) 与原 complex 切片逐位一致，
而把 complex128 重新量化 int16 会引入舍入误差。落盘的是原始 int16 子区间。
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np

CONTRACT_DIR = r"F:\嵌赛\fix10class24_independent_rx_delivery_fix1_work\scripts"
sys.path.insert(0, CONTRACT_DIR)
import radioml_independent_rx_contract as IRX  # noqa: E402
import radioml_dualsdr_common as C           # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from reproduce_fix2_diagnosis import (       # noqa: E402
    FS, K_TOTAL, CAPTURE_DIR, read_raw_i16, locate_preamble,
)
from radioml_independent_rx_recovery_fix2 import (  # noqa: E402
    estimate_public_reference_fix2, frac_delay_sinc,
)

V2_UNSCALE = 1.0 / 71.609111379029812
OUT = Path(__file__).parent.parent / "results" / "fix2_cpp_ref"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def tensor_to_bytes(iq: np.ndarray) -> bytes:
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    x = np.empty((2, len(iq)), dtype="<f4")
    x[0] = iq.real.astype("<f4")
    x[1] = iq.imag.astype("<f4")
    return x.tobytes()


def recover_v2_fix2(rx: np.ndarray, est: dict) -> np.ndarray:
    """fix2 恢复 + v2 反缩放（与板端 fr.unscale = 1/71.609... 逐字一致）。"""
    timing = est["timing_offset"]
    aligned = np.roll(rx, -timing) if timing else rx
    n = np.arange(K_TOTAL, dtype=np.float64)
    derot = aligned * np.exp(-1j * 2.0 * np.pi * est["coarse_cfo_hz"] * n / FS)
    payload = derot[IRX.K_PAYLOAD_START:IRX.K_PAYLOAD_START + IRX.K_PAYLOAD_COMPLEX]
    wl = IRX.wide_linear_inverse(payload, est["a"], est["b"])
    shifted = frac_delay_sinc(wl, -est["fractional_timing"])
    return shifted[:IRX.GEN.SAMPLE_LENGTH] * V2_UNSCALE


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    metric = ["sid\ttiming_offset\tcoarse_cfo_hz\tfractional_timing\t"
              "cfo_preamble_legacy_hz\ttraining_residual\ttraining_residual_rel"]
    sha = ["sid\tmodel_input_sha256"]
    for sid in range(1, 25):
        inter = read_raw_i16(CAPTURE_DIR / ("%d.raw.i16" % sid))
        rx_full = C.deinterleave_int16(inter)
        off, _ = locate_preamble(rx_full, len(rx_full) - K_TOTAL)
        # 精确切片 int16（deinterleave 后 slice == slice int16 再 deinterleave）
        sliced_i16 = inter[2 * off: 2 * off + 2 * K_TOTAL]
        (OUT / ("%d.burst.i16" % sid)).write_bytes(sliced_i16.tobytes())

        rx_burst = rx_full[off:off + K_TOTAL].copy()
        est = estimate_public_reference_fix2(rx_burst)
        mi_sha = sha256_bytes(tensor_to_bytes(recover_v2_fix2(rx_burst, est)))

        metric.append("%d\t%d\t%.9g\t%.17g\t%.9g\t%.17g\t%.17g" % (
            sid, est["timing_offset"], est["coarse_cfo_hz"],
            est["fractional_timing"], est["cfo_preamble_legacy_hz"],
            est["training_residual"], est["training_residual_rel"]))
        sha.append("%d\t%s" % (sid, mi_sha))
        print("sid=%02d off=%d cfo=%.1f tau=%+.2f rr=%.6f mi_sha=%s" %
              (sid, off, est["coarse_cfo_hz"], est["fractional_timing"],
               est["training_residual_rel"], mi_sha))

    (OUT / "metrics.tsv").write_text("\n".join(metric) + "\n", encoding="utf-8")
    (OUT / "model_input_sha.tsv").write_text("\n".join(sha) + "\n", encoding="utf-8")
    print("\nwrote %s/metrics.tsv + model_input_sha.tsv + 24 burst slices" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
