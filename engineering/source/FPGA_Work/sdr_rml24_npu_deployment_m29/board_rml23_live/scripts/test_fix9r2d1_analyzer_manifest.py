#!/usr/bin/env python3
"""fix9r2d1 analyzer manifest + circular-slice regression.

Covers the two offline-analyzer defects fixed in fix9r2d1:

  * Task A -- manifest long-name -> internal short-name mapping (no more
    `w[kind] = x` KeyError on `cycle0`); strict 8-key assertion + fail-closed
    on unknown / duplicate / missing kinds, with filename in the message.
  * Task B -- `circular_slice(x, start, length)`: modular circular sampling of a
    PERIOD-length complex vector, never silently truncating when the timing
    offset wraps past the end of the period.

The manifest-related checks all go through the formal entry point
`analyze_manifests(...)` against REAL temporary .f32 files + TSV manifests (the
exact board column layouts).  `circular_slice` and the duplicate-internal-key
case are exercised as focused unit checks.

Run:  python -I scripts/test_fix9r2d1_analyzer_manifest.py
"""
import contextlib
import hashlib
import io
import os
import shutil
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_fix9r2d_capture as mod

TRAIN_LEN = mod.TRAIN_LEN
PAYLOAD_LEN = mod.PAYLOAD_LEN
PAYLOAD_START = mod.PAYLOAD_START
PERIOD = mod.PERIOD
KIND_MAP = mod.KIND_MAP
circular_slice = mod.circular_slice
load_all_waveforms = mod.load_all_waveforms
analyze_manifests = mod.analyze_manifests
self_test = mod.self_test

KINDS = list(KIND_MAP.keys())   # the 8 manifest long names, in the module's order

# Exact board manifest column layouts (iq_rf_loopback_23class_fix9r.hpp).
WAVEFORM_HEADER = ["file_name", "kind", "path", "sha256", "complex_samples", "rms",
                   "format", "mem_slice_sha256", "mem_equality", "start_index",
                   "length", "cycle_index", "linear_offset", "circular_offset"]
CAPTURE_HEADER = ["file_name", "capture_sha256", "capture_complex", "frame_start_abs",
                  "training_start", "training_end", "payload_start", "payload_end",
                  "full_frame_start", "full_frame_end", "cycle_period", "cycle0_start",
                  "cycle1_start", "linear_offset", "circular_offset", "rms", "dc_re",
                  "dc_im", "peak", "clip", "cfo_hz", "sro_ppm", "gain_mag", "phase_deg",
                  "timing_offset", "training_corr", "training_residual", "complete"]

_results = []


def check(name, cond, detail=""):
    _results.append((name, bool(cond)))
    print("  %-4s %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  " + detail) if detail else ""))


def finalize():
    npass = sum(1 for _, ok in _results if ok)
    nfail = len(_results) - npass
    print("%d/%d PASS%s" % (npass, len(_results),
                            " (%d FAIL)" % nfail if nfail else ""))
    return 0 if nfail == 0 else 1


def zc(n, amp=1.0):
    k = np.arange(n, dtype=np.float64)
    ph = -np.pi * k * (k + 1) / n
    return (amp * np.exp(1j * ph)).astype(np.complex128)


def write_f32(path, x):
    x = np.ascontiguousarray(np.asarray(x, dtype=np.complex128))
    inter = x.view(np.float64).astype(np.float32)   # [re0, im0, re1, im1, ...]
    inter.tofile(path)
    return hashlib.sha256(inter.tobytes()).hexdigest()


def default_meta(off):
    return {"timing_offset": off, "gain_mag": 1.0, "phase_deg": 0.0,
            "cfo_hz": 0.0, "sro_ppm": 0.0, "complete": 1}


def sample_waveforms(off, seed=2026, distort_cycle1=False):
    """Identity-channel sample (rx == ref) at a given within-cycle timing offset.

    full is the *aligned* frame: training at [0:TRAIN_LEN], payload at
    [PAYLOAD_START:PAYLOAD_START+PAYLOAD_LEN].  The raw cycles are the full frame
    rotated by `off` (cyclic TX, stable channel), so circular_slice(cycle, off, …)
    recovers the aligned training/payload exactly.
    """
    rng = np.random.default_rng(seed)
    train = zc(TRAIN_LEN)
    pay = (rng.standard_normal(PAYLOAD_LEN)
           + 1j * rng.standard_normal(PAYLOAD_LEN)).astype(np.complex128)
    full = np.zeros(PERIOD, dtype=np.complex128)
    full[:TRAIN_LEN] = train
    full[PAYLOAD_START:PAYLOAD_START + PAYLOAD_LEN] = pay
    cycle0 = np.roll(full, off)
    cycle1 = np.roll(full, off)
    if distort_cycle1:
        cycle1 = cycle1 + 0.5 * (rng.standard_normal(PERIOD)
                                 + 1j * rng.standard_normal(PERIOD)).astype(np.complex128)
    return {
        "expected_training": train.copy(),
        "raw_aligned_rx_training": full[:TRAIN_LEN].copy(),
        "raw_aligned_rx_payload": full[PAYLOAD_START:PAYLOAD_START + PAYLOAD_LEN].copy(),
        "raw_aligned_rx_full_frame": full.copy(),
        "raw_cycle_0_full_frame": cycle0,
        "raw_cycle_1_full_frame": cycle1,
        "expected_payload": pay.copy(),
        "provisional_recovered_payload": pay.copy(),
    }


def materialize_sample(dirpath, fn, wf):
    rows = {}
    for kind in KINDS:
        x = wf[kind]
        path = os.path.join(dirpath, "%s_%s.f32" % (fn, kind))
        sha = write_f32(path, x)
        rows[kind] = {"path": path, "sha256": sha, "mem_equality": 1,
                      "complex_samples": x.size,
                      "rms": float(np.sqrt(np.mean(np.abs(x) ** 2)))}
    return rows


def write_wave_manifest(path, wave_rows):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(WAVEFORM_HEADER) + "\n")
        for fn in sorted(wave_rows):
            for kind in sorted(wave_rows[fn]):
                r = wave_rows[fn][kind]
                f.write("\t".join([
                    fn, kind, r["path"], r["sha256"], str(r["complex_samples"]),
                    "%.6f" % r["rms"], "f32", r["sha256"], str(r["mem_equality"]),
                    "0", str(r["complex_samples"]), "0", "0", "0"]) + "\n")


def write_capture_manifest(path, cap_rows):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(CAPTURE_HEADER) + "\n")
        for fn in sorted(cap_rows):
            m = cap_rows[fn]
            f.write("\t".join([
                fn, "x", "0", "0", "0", "0", "0", "0", "0", "0", str(PERIOD),
                "0", str(PERIOD), "0", "0", "0", "0", "0", "0", "0",
                "%.6f" % m["cfo_hz"], "%.6f" % m["sro_ppm"],
                "%.6f" % m["gain_mag"], "%.6f" % m["phase_deg"],
                str(m["timing_offset"]), "0", "0", str(m["complete"])]) + "\n")


def run_analyzer(wp, cp):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        outcome = analyze_manifests(wp, cp)
    return outcome, buf.getvalue()


def run_full_flow(off, distort_cycle1=False, seed_base=2026):
    """Self-contained 2-sample fixture at the given offset -> (outcome, stdout)."""
    d = tempfile.mkdtemp(prefix="f9r2d1_flow_")
    try:
        wave_rows, cap_rows = {}, {}
        for i, fn in enumerate(["f1", "f2"]):
            wf = sample_waveforms(off, seed=seed_base + i, distort_cycle1=distort_cycle1)
            wave_rows[fn] = materialize_sample(d, fn, wf)
            cap_rows[fn] = default_meta(off)
        wp = os.path.join(d, "route_f_fix9r2d_waveforms.tsv")
        cp = os.path.join(d, "route_f_fix9r2d_capture.tsv")
        write_wave_manifest(wp, wave_rows)
        write_capture_manifest(cp, cap_rows)
        return run_analyzer(wp, cp)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    # ------------------------------------------------------------------
    # Case 1 / 15 / 18: valid clean identity set (off=0) through the formal entry.
    # ------------------------------------------------------------------
    outcome, out = run_full_flow(0)
    verdicts = [r["metrics"]["verdict"] for r in outcome.get("per_file", [])]

    check("1 真实8个长kind名称正确映射 (accepted=True)",
          outcome["accepted"] is True, "accepted=%r" % outcome["accepted"])
    check("1 两份文件各自产出判责且均为 STABLE_LTI_CHANNEL",
          len(verdicts) == 2 and all(v == "STABLE_LTI_CHANNEL" for v in verdicts),
          "verdicts=%s" % verdicts)
    check("1 KIND_MAPPING token (external_kinds=8 internal_keys=8)",
          "FIX9R2D1_KIND_MAPPING result=PASS external_kinds=8 internal_keys=8" in out)
    check("1 CIRCULAR_SLICE token (training 1024,1024 payload 53760,53760)",
          "FIX9R2D1_CIRCULAR_SLICE result=PASS training_lengths=1024,1024 payload_lengths=53760,53760" in out)
    check("18 全程无 KeyError/异常（正式入口 valid 流）",
          "KeyError" not in out and "Traceback" not in out)

    check("15 两个周期完全一致 -> STABLE_LTI_CHANNEL",
          all(v == "STABLE_LTI_CHANNEL" for v in verdicts), "verdicts=%s" % verdicts)

    # ------------------------------------------------------------------
    # Structural rejection cases (fail-closed) through the formal entry.
    # ------------------------------------------------------------------
    d = tempfile.mkdtemp(prefix="f9r2d1_rej_")
    try:
        wave_rows, cap_rows = {}, {}
        for i, fn in enumerate(["f1", "f2"]):
            wf = sample_waveforms(0, seed=2026 + i)
            wave_rows[fn] = materialize_sample(d, fn, wf)
            cap_rows[fn] = default_meta(0)

        def run_set(tag):
            wp = os.path.join(d, "w_%s.tsv" % tag)
            cp = os.path.join(d, "c_%s.tsv" % tag)
            write_wave_manifest(wp, wave_rows)
            write_capture_manifest(cp, cap_rows)
            return run_analyzer(wp, cp)

        # case 2: missing raw_cycle_0_full_frame (remove from f1)
        saved = wave_rows["f1"].pop("raw_cycle_0_full_frame")
        o2, out2 = run_set("missing_kind")
        check("2 缺少 raw_cycle_0_full_frame -> REJECTED (点名 kind)",
              not o2["accepted"] and any("raw_cycle_0_full_frame" in p for p in o2["problems"]),
              "; ".join(o2["problems"][:2]))
        wave_rows["f1"]["raw_cycle_0_full_frame"] = saved

        # case 3: unknown kind (a 9th long name) -> REJECTED (点名 kind)
        wave_rows["f1"]["not_a_real_kind"] = dict(saved)
        o3, out3 = run_set("unknown_kind")
        check("3 未知kind -> REJECTED (点名未知 kind)",
              not o3["accepted"] and any("not_a_real_kind" in p for p in o3["problems"]),
              "; ".join(o3["problems"][:2]))
        del wave_rows["f1"]["not_a_real_kind"]

        # case 5: wrong length (a truncated raw slice)
        short_path = os.path.join(d, "f1_short.f32")
        np.zeros(100, dtype="<f4").tofile(short_path)   # 50 complex != any want
        wave_rows["f1"]["raw_aligned_rx_training"]["path"] = short_path
        o5, out5 = run_set("wrong_len")
        check("5 错误长度 -> REJECTED (samples/want)",
              not o5["accepted"] and any("samples (want" in p for p in o5["problems"]),
              "; ".join(o5["problems"][:2]))

        # case 6: provenance equality=0 -> REJECTED
        wave_rows["f1"]["raw_aligned_rx_training"]["path"] = os.path.join(
            d, "f1_raw_aligned_rx_training.f32")
        wave_rows["f2"]["raw_aligned_rx_training"]["mem_equality"] = 0
        o6, out6 = run_set("equality0")
        check("6 provenance equality=0 -> REJECTED (mem_equality)",
              not o6["accepted"] and any("mem_equality=0" in p for p in o6["problems"]),
              "; ".join(o6["problems"][:2]))
        wave_rows["f2"]["raw_aligned_rx_training"]["mem_equality"] = 1

        # case 7: capture complete=0 -> REJECTED
        cap_rows["f2"]["complete"] = 0
        o7, out7 = run_set("complete0")
        check("7 capture complete=0 -> REJECTED (capture_complete)",
              not o7["accepted"] and any("capture_complete=0" in p for p in o7["problems"]),
              "; ".join(o7["problems"][:2]))
        cap_rows["f2"]["complete"] = 1
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # ------------------------------------------------------------------
    # Wrap cases through the formal entry (off -> circular slice, still LTI).
    # ------------------------------------------------------------------
    def wrap_flow(off, tag):
        o, oo = run_full_flow(off)
        vs = [r["metrics"]["verdict"] for r in o.get("per_file", [])]
        check("%s (off=%d) -> accepted + STABLE_LTI + 长度 token" % (tag, off),
              o["accepted"] and all(v == "STABLE_LTI_CHANNEL" for v in vs)
              and "FIX9R2D1_CIRCULAR_SLICE result=PASS training_lengths=1024,1024 payload_lengths=53760,53760" in oo,
              "verdicts=%s" % vs)

    wrap_flow(PERIOD // 2, "8  timing位于周期中央")
    wrap_flow(PERIOD - 100, "9  timing靠近周期尾部")
    wrap_flow(PERIOD - 100, "10 training跨周期")   # PERIOD-100 > PERIOD-TRAIN_LEN
    wrap_flow(50000, "11 payload跨周期")           # 50000 > PERIOD - PAYLOAD_START - PAYLOAD_LEN

    # ------------------------------------------------------------------
    # Two cycles differ (non-stationary) -> CYCLE_TO_CYCLE_NONSTATIONARY.
    # ------------------------------------------------------------------
    o16, _ = run_full_flow(0, distort_cycle1=True)
    vs16 = [r["metrics"]["verdict"] for r in o16.get("per_file", [])]
    check("16 两个周期不一致 -> CYCLE_TO_CYCLE_NONSTATIONARY",
          o16["accepted"] and all(v == "CYCLE_TO_CYCLE_NONSTATIONARY" for v in vs16),
          "verdicts=%s" % vs16)

    # ------------------------------------------------------------------
    # circular_slice unit checks (12 / 13 / 14 + real risk case).
    # ------------------------------------------------------------------
    x = np.arange(PERIOD, dtype=np.complex128)
    # case 14: length is always exact, content matches modular sampling
    for start, length in [(0, TRAIN_LEN), (5, TRAIN_LEN), (PERIOD - 5, 10),
                          (PERIOD // 2, PAYLOAD_LEN), (PERIOD + 100, 50)]:
        y = circular_slice(x, start, length)
        if y.size != length:
            check("14 返回长度始终准确 (start=%d len=%d)" % (start, length), False,
                  "got size %d" % y.size)
            break
    else:
        check("14 返回长度始终准确 (0/-5/tail/mid/>PERIOD)", True)

    # case 12: negative start
    y_neg = circular_slice(x, -5, 10)
    check("12 负start -> 循环取模且长度准确",
          y_neg.size == 10 and y_neg[0] == x[PERIOD - 5] and y_neg[5] == x[0])

    # case 13: start > one period
    y_big = circular_slice(x, PERIOD + 100, 50)
    check("13 start大于一个周期 -> 取模且首元素=x[100]",
          y_big.size == 50 and y_big[0] == x[100])

    # real risk case: circ + PAYLOAD_START + PAYLOAD_LEN > PERIOD
    circ = PERIOD - 100
    old_plain = x[circ + PAYLOAD_START:circ + PAYLOAD_START + PAYLOAD_LEN]
    new_circ = circular_slice(x, circ + PAYLOAD_START, PAYLOAD_LEN)
    check("risk 旧普通切片在跨周期时截断(短于 PAYLOAD_LEN)",
          old_plain.size < PAYLOAD_LEN, "old=%d" % old_plain.size)
    check("risk circular_slice 跨周期返回完整 %d" % PAYLOAD_LEN,
          new_circ.size == PAYLOAD_LEN)

    # ------------------------------------------------------------------
    # Case 4: duplicate internal key (two long kinds -> same internal key).
    # ------------------------------------------------------------------
    orig_map = dict(mod.KIND_MAP)
    try:
        dup = dict(orig_map)
        dup["raw_cycle_1_full_frame"] = dup["raw_cycle_0_full_frame"]  # both -> cycle0
        mod.KIND_MAP = dup
        entries = {k: {"path": "x", "sha256": "y", "mem_equality": 1} for k in KINDS}
        w, probs = load_all_waveforms(entries, label="f1")
        check("4 重复internal key -> fail (点名两个 kind)",
              any("duplicate internal key" in p for p in probs),
              "; ".join(p for p in probs if "duplicate" in p))
    finally:
        mod.KIND_MAP = orig_map

    # ------------------------------------------------------------------
    # Case 17: the original 7-verdict self-test still passes (no regression).
    # ------------------------------------------------------------------
    fails = self_test()
    check("17 原有 7 判责 self-test 无回归", fails == 0, "fails=%d" % fails)

    return finalize()


if __name__ == "__main__":
    sys.exit(main())
