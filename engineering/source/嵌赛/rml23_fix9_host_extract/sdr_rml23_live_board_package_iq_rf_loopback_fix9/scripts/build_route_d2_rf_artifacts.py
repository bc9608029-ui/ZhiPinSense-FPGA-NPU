#!/usr/bin/env python3
"""build_route_d2_rf_artifacts.py -- fix9 Task B/C: Route F fix9 23-class RF-
loopback artifacts from the frozen RadioML Stage G extraction.

Reads the extract_radioml_stage_g.py output (input_*.bin + manifest_a.tsv) and
produces, per sample, the Route D2 NON-training reconstruction artefacts the
board needs for the physical IQ RF loopback / 23-class accuracy run:

  quantized_d2_2p56m_%06d.ci16  interleaved int16 LE (I,Q,I,Q...), AC-ONLY, the
                                per-file DC is REMOVED and the AC is normalised to
                                global K int16 RMS counts (K=2048 default), then
                                x20-interpolated to 2.56 MSPS (53760 complex).
                                This is the exact TX waveform the board streams
                                through the Pluto.
  recovered_tensor_d2_%06d.f32  [2,1024] fp32 (8192 bytes), the D2 reference: the
                                AC re-mapped + the original DC restored -- i.e.
                                the near-lossless recovered tensor the board
                                compares / window-aligns against.
  route_d2_rf_manifest.tsv      24 columns, one row per written sample, carrying
                                the per-file D2 restore constants (original_dc_i/q,
                                ac_rms, rec_scale) and every SHA the board needs
                                to fail-closed verify before TX.

The 24 source classes map to the 23 deployed classes via the frozen AM-merge rule
(rml23::kSourceToDeployed): source 17 (AM-SSB-WC) and 18 (AM-SSB-SC) both deploy
to 17 (AM-SSB); the AM-SSB deployed class pools its two source sub-classes.  The
global K is chosen ONLY from an independent, unlabelled CALIBRATION subset (never
a label, never the holdout): K=2048 (the RF safe TX RMS) is preferred, and if it
clips a calibration sample the largest clip-free smaller K is re-selected.  No
per-class K is ever used.  If a sample still clips at the chosen K the builder
FAIL-CLOSES (no silent saturation).

Calibration and holdout are SEPARATED: the builder writes both, and the
split_role column marks each row "calibration" or "holdout", so the board can
estimate its ONE global RF complex gain on a genuine independent subset.

Never modifies any Route A / Route D file, never reads a label to choose K or RF
parameters, never runs the NPU.  Pure stdlib + numpy (reuses the reconstruction
primitives from analyze_route_d2_4ask.py).

Usage:
    python3 -I scripts/build_route_d2_rf_artifacts.py \
        --bin-dir /root/rml23_route_d2_extract --out-dir /root/rml23_route_f_fix9 \
        --calib-count 8 --holdout-count 30        # formal: 690 holdout
    python3 -I scripts/build_route_d2_rf_artifacts.py \
        --bin-dir /root/rml23_route_d2_extract --out-dir /root/rml23_route_f_fix9 \
        --smoke                                    # smoke: 46 holdout
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_route_d2_4ask as A

N_SAMPLES = A.N_SAMPLES
KADC = A.KADC
INTERP_FACTOR = A.INTERP_FACTOR
DEFAULT_GUARD = A.DEFAULT_GUARD
DEFAULT_EDGE = "zero"

# Frozen 24 -> 23 deployed mapping (== rml23::kSourceToDeployed).  AM-SSB-WC(17)
# and AM-SSB-SC(18) both deploy to AM-SSB(17).
SOURCE_TO_DEPLOYED = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
                      17, 17, 18, 19, 20, 21, 22]
DEPLOYED_NAMES = ["OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK",
                  "32PSK", "16APSK", "32APSK", "64APSK", "128APSK", "16QAM",
                  "32QAM", "64QAM", "128QAM", "256QAM", "AM-SSB", "AM-DSB-WC",
                  "AM-DSB-SC", "FM", "GMSK", "OQPSK"]
DEPLOYED_TO_SOURCES = {}
for _s, _d in enumerate(SOURCE_TO_DEPLOYED):
    DEPLOYED_TO_SOURCES.setdefault(_d, []).append(_s)

DEFAULT_K = 2048.0
K_CANDIDATES = [2048.0, 1024.0, 512.0, 256.0]

MANIFEST_HEADER = [
    "sample_index", "source_index", "raw24_class", "deployed23_class",
    "modulation", "snr_db", "split_role", "global_K", "original_dc_i",
    "original_dc_q", "ac_rms", "rec_scale", "complex_count", "sample_rate",
    "tx_rms", "tx_peak", "clip_count", "edge_policy", "guard",
    "original_sha256", "quantized_sha256", "recovered_tensor_sha256",
    "quantized_file", "recovered_tensor_file",
]
SAMPLE_RATE_HZ = 2560000


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def split_across(n: int, sources: list) -> list:
    """Split n samples as evenly as possible across len(sources) source classes
    (the AM-SSB deployed class pools its two source sub-classes)."""
    q, rem = divmod(n, len(sources))
    return [q + (1 if i < rem else 0) for i in range(len(sources))]


def select_global_k(calib: list, k_candidates: list = K_CANDIDATES) -> float:
    """Choose the largest global K whose D2 reconstruction clips NO calibration
    sample (unlabelled, calibration subset only).  K=2048 is preferred (the RF
    safe TX RMS); if it clips a calibration sample, a smaller K is re-selected.
    Never per-class, never label-dependent."""
    for K in k_candidates:
        clip_free = True
        for x in calib:
            if A.reconstruct(x, "D2", K)["clip_count"] > 0:
                clip_free = False
                break
        if clip_free:
            return K
    raise RuntimeError("no clip-free global K among %r (calibration clips at "
                       "every candidate)" % (k_candidates,))


def build_one(x, K: float, edge: str = DEFAULT_EDGE,
              guard: int = DEFAULT_GUARD) -> dict:
    """Build the per-sample D2 artifact dict for ONE original 1024-complex."""
    r = A.reconstruct(x, "D2", K, edge=edge, guard=guard)
    if r["clip_count"] > 0:
        raise RuntimeError("clip_count=%d at K=%.0f: fail-closed, no silent "
                           "saturation" % (r["clip_count"], K))
    iq = r["iq"]
    return {
        "iq": iq,
        "recovered": A.recovered_tensor_1024(x, r["recovered"]),
        "dc_i": r["dc_i"],
        "dc_q": r["dc_q"],
        "ac_rms": r["ac_rms"],
        "rec_scale": r["rec_scale"],
        "tx_rms": float(np.sqrt(np.mean(iq.astype(np.float64) ** 2))),
        "tx_peak": float(np.max(np.abs(iq.astype(np.float64)))),
        "clip_count": r["clip_count"],
        "complex_count": iq.size // 2,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bin-dir", default=None)
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--calib-count", type=int, default=8)
    ap.add_argument("--holdout-count", type=int, default=30)
    ap.add_argument("--smoke", action="store_true",
                    help="smoke mode: 2 holdout frames per deployed class (46)")
    ap.add_argument("--k", type=float, default=None,
                    help="override the global K (skip calibration K search)")
    ap.add_argument("--edge-policy", default=DEFAULT_EDGE)
    ap.add_argument("--guard", type=int, default=DEFAULT_GUARD)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if not args.bin_dir or not args.out_dir:
        ap.error("--bin-dir and --out-dir are required unless --self-test")
    if args.calib_count < 1 or args.holdout_count < 1:
        ap.error("--calib-count/--holdout-count must be >= 1")
    holdout_count = 2 if args.smoke else args.holdout_count

    manifest = args.manifest or os.path.join(args.bin_dir, "manifest_a.tsv")
    rows = A.parse_manifest(manifest, args.bin_dir)

    by_source = {}
    for r in rows:
        by_source.setdefault(r["class_index"], []).append(r)

    # Collect (tensor, raw24, deployed, source_index, snr_db, role, row) per
    # deployed class, splitting the per-deployed counts across its source classes.
    samples = []
    for d in range(len(DEPLOYED_NAMES)):
        sources = DEPLOYED_TO_SOURCES[d]
        calib_split = split_across(args.calib_count, sources)
        holdout_split = split_across(holdout_count, sources)
        for si, src in enumerate(sources):
            have = by_source.get(src, [])
            need = calib_split[si] + holdout_split[si]
            if len(have) < need:
                ap.error("deployed %s (source %d) needs %d frames, manifest has %d"
                         % (DEPLOYED_NAMES[d], src, need, len(have)))
            for j, r in enumerate(have[:need]):
                role = "calibration" if j < calib_split[si] else "holdout"
                x = A.read_tensor(os.path.join(args.bin_dir, r["bin_file"]))
                samples.append((x, src, d, r["source_index"], r["snr_db"],
                                role, r))

    calib = [x for (x, _s, _d, _i, _n, role, _r) in samples
             if role == "calibration"]
    holdout = [(x, s, d, i, n, r) for (x, s, d, i, n, role, r) in samples
               if role == "holdout"]

    K = args.k if args.k is not None else select_global_k(calib)

    os.makedirs(args.out_dir, exist_ok=True)
    manifest_rows = []
    n_clip = 0
    for out_idx, (x, raw24, dep23, sidx, snr, row) in enumerate(holdout):
        role = "holdout"
        art = build_one(x, K, edge=args.edge_policy, guard=args.guard)
        qname = "quantized_d2_2p56m_%06d.ci16" % out_idx
        rname = "recovered_tensor_d2_%06d.f32" % out_idx
        qpath = os.path.join(args.out_dir, qname)
        rpath = os.path.join(args.out_dir, rname)
        art["iq"].tofile(qpath)
        art["recovered"].tofile(rpath)
        q_sha = sha256_file(qpath)
        r_sha = sha256_file(rpath)
        manifest_rows.append([
            str(out_idx), str(sidx), str(raw24), str(dep23),
            A.INDEX_TO_CLASS[raw24], "%.1f" % snr, role, "%.0f" % K,
            "%.9g" % art["dc_i"], "%.9g" % art["dc_q"], "%.9g" % art["ac_rms"],
            "%.9g" % art["rec_scale"], str(art["complex_count"]),
            str(SAMPLE_RATE_HZ), "%.6f" % art["tx_rms"], "%.6f" % art["tx_peak"],
            str(art["clip_count"]), args.edge_policy, str(args.guard),
            row["bin_sha256"], q_sha, r_sha, qname, rname,
        ])

    # Write the calibration artifacts too, so the board has a genuine independent
    # RF-gain calibration subset (split_role=calibration).  The chosen K already
    # guarantees the calibration subset is clip-free.
    for cal_idx, (x, raw24, dep23, sidx, snr, row) in enumerate(
            [(x, s, d, i, n, r) for (x, s, d, i, n, role, r) in samples
             if role == "calibration"]):
        art = build_one(x, K, edge=args.edge_policy, guard=args.guard)
        qname = "quantized_d2_2p56m_cal_%06d.ci16" % cal_idx
        rname = "recovered_tensor_d2_cal_%06d.f32" % cal_idx
        qpath = os.path.join(args.out_dir, qname)
        rpath = os.path.join(args.out_dir, rname)
        art["iq"].tofile(qpath)
        art["recovered"].tofile(rpath)
        manifest_rows.append([
            str(len(holdout) + cal_idx), str(sidx), str(raw24), str(dep23),
            A.INDEX_TO_CLASS[raw24], "%.1f" % snr, "calibration", "%.0f" % K,
            "%.9g" % art["dc_i"], "%.9g" % art["dc_q"], "%.9g" % art["ac_rms"],
            "%.9g" % art["rec_scale"], str(art["complex_count"]),
            str(SAMPLE_RATE_HZ), "%.6f" % art["tx_rms"], "%.6f" % art["tx_peak"],
            str(art["clip_count"]), args.edge_policy, str(args.guard),
            row["bin_sha256"], sha256_file(qpath), sha256_file(rpath),
            qname, rname,
        ])

    with open(os.path.join(args.out_dir, "route_d2_rf_manifest.tsv"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join(MANIFEST_HEADER) + "\n")
        for mr in manifest_rows:
            fh.write("\t".join(mr) + "\n")

    with open(os.path.join(args.out_dir, "route_d2_rf_build.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump({
            "global_K": K,
            "k_auto_selected": args.k is None,
            "calib_count_per_deployed": args.calib_count,
            "holdout_count_per_deployed": holdout_count,
            "smoke": bool(args.smoke),
            "num_calibration": args.calib_count * len(DEPLOYED_NAMES),
            "num_holdout": len(holdout),
            "edge_policy": args.edge_policy,
            "guard": args.guard,
            "source_to_deployed": SOURCE_TO_DEPLOYED,
            "deployed_names": DEPLOYED_NAMES,
        }, fh, indent=2)

    print("ROUTE_D2_RF_BUILD global_K=%.0f calib=%d holdout=%d (smoke=%s) "
          "clip_rejections=%d result=PASS"
          % (K, args.calib_count * len(DEPLOYED_NAMES), len(holdout),
             "1" if args.smoke else "0", n_clip))
    print("wrote %d artifacts + route_d2_rf_manifest.tsv to %s"
          % (len(manifest_rows), args.out_dir))
    return 0


def self_test() -> int:
    npass = 0
    rng = np.random.default_rng(3)

    # 1. build_one: AC-only ci16 at 53760 complex (215040 bytes) + 8192-byte
    # recovered tensor with DC restored (near-lossless for a clean 4ASK).
    x = A.synth_4ask(rng=rng)
    art = build_one(x, 2048.0)
    if (art["iq"].size == 2 * (A.DEFAULT_GUARD + N_SAMPLES + A.DEFAULT_GUARD) * INTERP_FACTOR
            and art["complex_count"] == 53760
            and art["recovered"].size == 2 * N_SAMPLES
            and art["clip_count"] == 0):
        npass += 1
        print("  OK  build_one sizes (ci16=53760cx, recovered=2048)")
    else:
        print("  BAD build_one sizes iq=%d rec=%d clip=%d"
              % (art["iq"].size, art["recovered"].size, art["clip_count"]))

    # 2. DC restored: recovered tensor == original (AC+DC), low NMSE.
    rec = art["recovered"][:N_SAMPLES] + 1j * art["recovered"][N_SAMPLES:]
    nmse = float(np.sum(np.abs(x - rec) ** 2)) / float(np.sum(np.abs(x) ** 2))
    if nmse < 1e-2:
        npass += 1
        print("  OK  D2 DC+AC restored nmse=%.3e" % nmse)
    else:
        print("  BAD D2 restored nmse=%.3e" % nmse)

    # 3. select_global_k prefers 2048 when it does not clip synthetic 4ASK.
    calib = [A.synth_4ask(rng=np.random.default_rng(i)) for i in range(6)]
    if select_global_k(calib) == 2048.0:
        npass += 1
        print("  OK  global K = 2048 (clip-free calibration)")
    else:
        print("  BAD global K selection")

    # 4. re-selection: a high-crest calibration sample clips at an overlarge K
    # (8192) and select_global_k re-selects the largest clip-free candidate.
    # D2 normalises AC by its own RMS, so clipping depends on crest factor, not
    # amplitude; the same loop re-selects if the DEFAULT 2048 ever clips.
    spike = np.zeros(N_SAMPLES, dtype=np.complex128)
    spike[0] = 40.0 + 0j
    spike = spike / float(np.sqrt(np.mean(np.abs(spike) ** 2)))  # crest ~32
    clip_at_8192 = A.reconstruct(spike, "D2", 8192.0)["clip_count"] > 0
    k2 = select_global_k([spike], k_candidates=[8192.0, 2048.0, 1024.0])
    if clip_at_8192 and k2 == 2048.0:
        npass += 1
        print("  OK  global K skips clipping 8192 -> re-selects %.0f" % k2)
    else:
        print("  BAD global K re-select clip@8192=%s got=%s" % (clip_at_8192, k2))

    # 5. 24->23 AM-merge: sources 17 and 18 both deploy to 17 (AM-SSB).
    if (SOURCE_TO_DEPLOYED[17] == 17 and SOURCE_TO_DEPLOYED[18] == 17
            and DEPLOYED_TO_SOURCES[17] == [17, 18]
            and len(DEPLOYED_NAMES) == 23
            and DEPLOYED_NAMES[17] == "AM-SSB"):
        npass += 1
        print("  OK  24->23 AM-merge (17,18 -> deployed 17 AM-SSB)")
    else:
        print("  BAD 24->23 AM-merge")

    # 6. split_across distributes an even per-deployed count across two sources.
    if split_across(30, [17, 18]) == [15, 15] and split_across(2, [17, 18]) == [1, 1]:
        npass += 1
        print("  OK  split_across (30 -> 15+15, 2 -> 1+1)")
    else:
        print("  BAD split_across")

    print("self-test: %d/6 correct" % npass)
    return 0 if npass == 6 else 1


if __name__ == "__main__":
    sys.exit(main())
