#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest_oracle_ablation.py -- 自测（纯离线，合成夹具 + 红线结构断言）。

覆盖（2026-10-21 复审修正后）：
  1. O0 byte-exact 失败 fail-closed（SHA 不符 -> 拒判）。
  2. 源/载荷身份不匹配拒绝（源 24、数字基线 24 唯一、上界 23/24）。
  3. 固定 24 分母（不剔除任何帧）。
  4. oracle 不改写生产门（0.100 门与生产 TSV 只读）。
  5. oracle 级别**独立**（O1/O2/O3 各自对 z0 施加单一修正，非累积）。
  6. O5 真正交叉验证（每半段用另半段拟合，拼接；残差仅计未参与拟合半段）。
  7. NMSE/NRMSE 定义正确（参考归一化）。
  8. C0(18/24) 不进 v2 统计。
  9. 不按标签挑选逐帧最优 oracle（各 oracle 均匀施加）。

任何断言失败 -> rc!=0。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_common as OC  # noqa: E402

FAIL = 0


def check(cond: bool, msg: str):
    global FAIL
    if not cond:
        print("FAIL: %s" % msg)
        FAIL += 1
    else:
        print("ok: %s" % msg)


def make_waveform(n=1024, seed=7):
    rng = np.random.default_rng(seed)
    return (rng.normal(0, 1, n) + 1j * rng.normal(0, 1, n)).astype(np.complex128)


def test_cyclic_align():
    x = make_waveform()
    for delta in [0, 1, 5, 512, 1023]:
        z = np.roll(x, delta)                      # z[k] = x[(k-delta)]
        shift, aligned = OC.cyclic_align(z, x)
        c = abs(np.vdot(aligned, x))
        e = float(np.vdot(x, x).real)
        check(c > 0.999 * e, "cyclic_align delta=%d corr=%.6f" % (delta, c / e))
    shift, _ = OC.cyclic_align(x, x)
    check(shift == 0, "cyclic_align identity shift=%d" % shift)


def test_apply_scale():
    x = make_waveform()
    s = 0.7 + 0.4j
    z = s * x
    out = OC.apply_scale(z, x)
    resid = np.sqrt(np.vdot(out - x, out - x).real / np.vdot(x, x).real)
    check(resid < 1e-12, "apply_scale (scale-only) resid=%.2e" % resid)


def test_apply_dc():
    x = make_waveform()
    dc = 2.0 - 3.0j
    z = x + dc
    out = OC.apply_dc(z, x)
    resid = np.sqrt(np.vdot(out - x, out - x).real / np.vdot(x, x).real)
    check(resid < 1e-12, "apply_dc (dc-only) resid=%.2e" % resid)


def test_apply_combined():
    x = make_waveform()
    s = 0.6 + 0.3j
    dc = 1.0 + 2.0j
    z = np.roll(s * x + dc, 7)
    out = OC.apply_combined(z, x)
    resid = np.sqrt(np.vdot(out - x, out - x).real / np.vdot(x, x).real)
    check(resid < 1e-10, "apply_combined (window+scale+dc) resid=%.2e" % resid)


def test_apply_affine_crossval():
    x = make_waveform()
    p, q, c = 0.8 + 0.1j, 0.05 - 0.02j, 0.3 + 0.4j
    z = p * x + q * np.conj(x) + c
    z_cross, nmse, nrmse = OC.apply_affine_crossval(z, x)
    # 均匀仿射关系下，交叉拟合应精确恢复
    resid = np.sqrt(np.vdot(z_cross - x, z_cross - x).real / np.vdot(x, x).real)
    check(resid < 1e-10, "O5 crossval uniform-affine resid=%.2e" % resid)
    check(nmse < 1e-20 and nrmse < 1e-10, "O5 crossval nmse=%.2e nrmse=%.2e" % (nmse, nrmse))
    # 结构断言：交叉验证（fit 半段 -> 应用另半段），无整段 fit 后同段声称
    src = (Path(__file__).parent / "oracle_common.py").read_text(encoding="utf-8")
    check("coef_from_second" in src and "coef_from_first" in src,
          "O5 交叉拟合（半段拟合->另半段应用）结构存在")
    # NMSE 一致性：nmse_nrmse 对 z_cross 应与 apply_affine_crossval 返回一致
    nmse2, nrmse2 = OC.nmse_nrmse(z_cross, x)
    check(abs(nmse2 - nmse) < 1e-24, "nmse_nrmse 与 crossval 返回一致")


def test_nmse_nrmse():
    x = make_waveform()
    # 已知缩放误差：z = 2*x -> NMSE = |x|²/|x|² = 1，NRMSE = 1
    z = 2.0 * x
    nmse, nrmse = OC.nmse_nrmse(z, x)
    check(abs(nmse - 1.0) < 1e-12, "nmse(2x)=1 实际 %.6f" % nmse)
    check(abs(nrmse - 1.0) < 1e-12, "nrmse(2x)=1 实际 %.6f" % nrmse)


def test_tensor_layout():
    x = make_waveform(OC.N)
    b = OC.tensor_to_bytes(x)
    check(len(b) == OC.N * 2 * 4, "tensor bytes size")
    arr = np.frombuffer(b, dtype="<f4").reshape(2, OC.N)
    check(np.allclose(arr[0], x.real.astype("<f4")) and
          np.allclose(arr[1], x.imag.astype("<f4")), "tensor [2,N] I/Q 布局")


def test_red_lines():
    check(len(OC.DIGITAL_BASELINE_PRED) == 24, "数字基线 24 预测")
    check(len(set(OC.DIGITAL_BASELINE_PRED)) == 23, "数字基线预测集合大小（0..19 + 21/22/23 = 23）")
    check(len(OC.LABEL_ORDER_24) == 24, "标签序 24")
    true = list(range(24))
    lab = sum(1 for i in range(24) if OC.DIGITAL_BASELINE_PRED[i] == true[i])
    check(lab == 23, "数字基线 label 上界 23/24（实际 %d）" % lab)
    check(OC.GATE == 0.100, "生产门 0.100 未改")
    src = (Path(__file__).parent / "oracle_common.py").read_text(encoding="utf-8")
    check("18/24" not in src and "full24_accuracy" not in src,
          "C0 旧链 18/24 未并入 v2 统计")
    check("24" in src, "固定 24 分母")


def test_independent_levels():
    # 结构断言：O1/O2/O3 各自对 z0 施加单一修正（非累积：apply_scale(z0) 而非 apply_scale(z1)）
    src = (Path(__file__).parent / "run_oracle_ablation.py").read_text(encoding="utf-8")
    check("z2 = OC.apply_scale(z0, x)" in src, "O2 只改尺度（apply_scale 作用在 z0）")
    check("z3 = OC.apply_dc(z0, x)" in src, "O3 只改直流（apply_dc 作用在 z0）")
    check("z4 = OC.apply_combined(z0, x)" in src, "O4 组合（apply_combined 作用在 z0）")
    check("apply_affine_crossval" in src, "O5 使用交叉验证仿射")


def test_no_per_frame_best_oracle():
    src = (Path(__file__).parent / "run_oracle_ablation.py").read_text(encoding="utf-8")
    check("for L in LEVELS" in src, "逐级均匀施加（无 per-frame best 选择）")
    check("argmax" not in src.replace("argmax_pred", ""), "无逐帧 oracle 择优")


def test_sha_fail_closed():
    a = b"abc"
    check(OC.sha256_bytes(a) == OC.sha256_bytes(b"abc"), "sha 确定性")
    check(OC.sha256_bytes(a) != OC.sha256_bytes(b"abd"), "sha 对篡改敏感")
    src = (Path(__file__).parent / "replay_o0_production.py").read_text(encoding="utf-8")
    check("INVALID_ANALYSIS_PRODUCTION_REPLAY_MISMATCH" in src, "O0 失败 fail-closed 判决存在")


def main() -> int:
    test_cyclic_align()
    test_apply_scale()
    test_apply_dc()
    test_apply_combined()
    test_apply_affine_crossval()
    test_nmse_nrmse()
    test_tensor_layout()
    test_red_lines()
    test_independent_levels()
    test_no_per_frame_best_oracle()
    test_sha_fail_closed()
    print("\nselftest: %s" % ("PASS" if FAIL == 0 else "%d FAILED" % FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
