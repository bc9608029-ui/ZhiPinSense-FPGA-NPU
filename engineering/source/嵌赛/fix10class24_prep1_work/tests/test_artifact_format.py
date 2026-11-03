"""fix10class24-prep1: on-disk artifact format + manifest/baseline tests."""

import os
import sys
from collections import Counter

import numpy as np

sys.dont_write_bytecode = True

COMPLEX_COUNT = 53760
CI16_BYTES = COMPLEX_COUNT * 2 * 2   # 215040
F32_BYTES = 2048 * 4                 # 8192


def _tsv_rows(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    header = lines[0].split("\t")
    rows = [ln.split("\t") for ln in lines[1:] if ln]
    return header, rows


def test_ci16_contiguous_little_endian(work_smoke):
    files = sorted(n for n in os.listdir(work_smoke)
                   if n.startswith("clean_") and n.endswith(".ci16"))
    assert len(files) == 24
    for n in files:
        b = open(os.path.join(work_smoke, n), "rb").read()
        assert len(b) == CI16_BYTES, n
        le = np.frombuffer(b, dtype="<i2")
        be = np.frombuffer(b, dtype=">i2")
        assert le.size == 2 * COMPLEX_COUNT
        assert le.flags.c_contiguous
        assert not np.array_equal(le, be), "ci16 bytes are not little-endian: " + n


def test_f32_contiguous_little_endian(work_smoke):
    src = sorted(n for n in os.listdir(work_smoke)
                 if n.startswith("source_") and n.endswith(".f32"))
    rec = sorted(n for n in os.listdir(work_smoke)
                 if n.startswith("recovered_tensor_") and n.endswith(".f32"))
    assert len(src) == 24 and len(rec) == 24
    for names in (src, rec):
        for n in names:
            b = open(os.path.join(work_smoke, n), "rb").read()
            assert len(b) == F32_BYTES, n
            le = np.frombuffer(b, dtype="<f4")
            be = np.frombuffer(b, dtype=">f4")
            assert le.size == 2048
            assert le.flags.c_contiguous
            assert not np.array_equal(le, be), "f32 bytes are not little-endian: " + n


def test_24_to_23_coverage_counts(work_smoke, build_mod):
    B = build_mod
    header, rows = _tsv_rows(os.path.join(work_smoke,
                                          "raw24_to_deployed23_mapping.tsv"))
    assert header == ["class_index", "raw24_label",
                      "deployed23_index", "deployed23_label"]
    assert len(rows) == 24
    assert sorted(r[1] for r in rows) == sorted(B.SOURCE_LABEL_ORDER_24)
    dep_indices = [int(r[2]) for r in rows]
    assert sorted(set(dep_indices)) == list(range(23))


def test_amssb_unique_merge_rule(work_smoke, build_mod):
    B = build_mod
    header, rows = _tsv_rows(os.path.join(work_smoke,
                                          "raw24_to_deployed23_mapping.tsv"))
    amssb = [r for r in rows if r[3] == "AM-SSB"]
    assert len(amssb) == 2
    assert {r[1] for r in amssb} == {"AM-SSB-WC", "AM-SSB-SC"}
    amssb_index = B.DEPLOYED_LABEL_ORDER_23.index("AM-SSB")
    assert all(int(r[2]) == amssb_index for r in amssb)
    counts = Counter(r[3] for r in rows)
    assert counts["AM-SSB"] == 2
    for k, c in counts.items():
        if k != "AM-SSB":
            assert c == 1


def test_baseline_schemas_not_mixed(work_smoke):
    ch, cr = _tsv_rows(os.path.join(work_smoke,
                                    "clean24_smoke_clean_baseline.tsv"))
    dh, dr = _tsv_rows(os.path.join(work_smoke, "clean24_smoke_baseline.tsv"))
    assert ch == ["source_index", "file_name", "sha256", "deployed_class",
                  "split_role", "frozen_baseline_pred"]
    assert dh == ["source_index", "original_sha256", "deployed_class",
                  "modulation", "split_role", "frozen_baseline_pred"]
    assert len(cr) == 24 and len(dr) == 24

    def _is_hex64(s):
        return len(s) == 64 and all(c in "0123456789abcdef" for c in s)

    for r in cr:
        assert r[1].endswith(".ci16") and "/" not in r[1] and "\\" not in r[1]
        assert _is_hex64(r[2])
        assert r[3] and r[4] == "holdout" and r[5]
    for r in dr:
        assert _is_hex64(r[1])
        assert r[3]  # modulation label non-empty
        assert not r[1].endswith(".ci16")
    # twin 1:1 rows across both baselines (same 24 source_index, same order)
    assert [r[0] for r in cr] == [r[0] for r in dr]
