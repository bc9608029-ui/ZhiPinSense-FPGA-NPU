#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pilot1_tx_manifest.py — M29-RML24-REALRF-FINETUNE-PILOT1 PC-side per-session manifest
loaders, pure stdlib (no iio / no subprocess).

Review 39e5 Blocker 2 splits the old 9-column "identity manifest" into THREE files so the
receiver (board) never holds class truth and the PC TX never hands the board a
`tx_payload_file` path.  This module loads the TWO files the PC needs:

  * `tx_manifest.tsv`           3-col **board-public identity** manifest.  Its SHA-256 is the
                                control-channel identity the board also computes from the
                                byte-identical board copy.  Columns:
                                  0 session_id   1 source_id   2 tx_payload_sha256
                                -> `Pilot1IdentityManifest` (provides `.sha256()`).
  * `tx_payload_manifest.tsv`   5-col **PC-private payload** manifest (never sent to the
                                board).  Keyed by capture sequence `seq` (0..239, the value
                                the board now sends as `source_index` over the wire).
                                  0 seq  1 session_id  2 source_id
                                  3 tx_payload_file  4 tx_payload_sha256
                                -> `Pilot1PayloadManifest` (provides `.lookup(seq)` returning
                                   {file_name, complex_count, quantized_sha256, ...}, the
                                   exact row interface `pc_tx_sdr_fix10.TxEngine` expects).

The ground-truth columns (class_index / class_name / dataset_index / split /
source_iq_sha256) live in the HOST ground-truth manifest `line_a/results/source_manifest_960.tsv`
and are joined OFFLINE by `source_id` after capture (judge / train / evaluate).  The board
never reads them, and the PC never sends them.

Both manifests are exported sorted by `source_id` (globally unique, ascending), with `seq`
equal to the 0-based row index; the board's 3-col loader iterates the same file order and
assigns the same `seq` as its per-sample loop index, so the mappings are deterministic and
identical on both ends.  The TX engine's `prepare_from_cache` still fail-closes by
cross-checking `file_name` and `quantized_sha256` against the identity the board sent.

Fail-closed: a wrong column count, a duplicate/out-of-order `seq`, a missing file entry, or
an empty manifest raises `ManifestError` (never a silent degradation).
"""

import hashlib

# iqrftrain::kPayloadComplex (iq_rf_training_frame.hpp) -- the pilot1 payload is
# always 53760 complex samples per source, regardless of class/session.
RF_PAYLOAD_COMPLEX = 53760

# 3-col board-public identity manifest (byte-identical to board_package/
# pilot1_tx_manifest.hpp `pilot1::tx_manifest_fields()`).
TX_MANIFEST_FIELD_COUNT = 3
TX_MANIFEST_HEADER = ["session_id", "source_id", "tx_payload_sha256"]

# 5-col PC-private payload manifest (never sent to the board).
TX_PAYLOAD_MANIFEST_FIELD_COUNT = 5
TX_PAYLOAD_MANIFEST_HEADER = [
    "seq", "session_id", "source_id", "tx_payload_file", "tx_payload_sha256",
]


class ManifestError(Exception):
    """A malformed pilot1 manifest."""


def _read_lines(path):
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8")
    return raw, [ln.rstrip("\r") for ln in text.split("\n")]


class Pilot1IdentityManifest:
    """3-col board-public identity manifest; only its byte SHA-256 is an identity."""

    def __init__(self, tx_payload_dir):
        self.dir = tx_payload_dir
        self.path = tx_payload_dir.rstrip("/\\") + "/tx_manifest.tsv"
        self.raw = b""
        self.rows = []   # list of source_id (file order == source_id ascending order)
        self._load()

    def _load(self):
        raw, lines = _read_lines(self.path)
        self.raw = raw
        header = None
        for line in lines:
            if line == "":
                continue
            f = line.split("\t")
            if header is None:
                header = f
                if header != TX_MANIFEST_HEADER:
                    raise ManifestError(
                        "pilot1 tx_manifest.tsv header mismatch: got %r" % (header,))
                continue
            if len(f) != TX_MANIFEST_FIELD_COUNT:
                raise ManifestError(
                    "pilot1 tx_manifest.tsv row has %d fields (want %d): %s"
                    % (len(f), TX_MANIFEST_FIELD_COUNT, line))
            source_id = f[1]
            tx_payload_sha256 = f[2]
            if len(tx_payload_sha256) != 64:
                raise ManifestError(
                    "pilot1 tx_manifest.tsv tx_payload_sha256 not 64-hex: %s" % line)
            self.rows.append(source_id)
        if header is None or not self.rows:
            raise ManifestError("pilot1 tx_manifest.tsv empty")
        if len(self.rows) != len(set(self.rows)):
            raise ManifestError("pilot1 tx_manifest.tsv duplicate source_id")

    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


class Pilot1PayloadManifest:
    """5-col PC-private payload manifest, keyed by capture sequence `seq` (0..239)."""

    def __init__(self, tx_payload_dir):
        self.dir = tx_payload_dir
        self.path = tx_payload_dir.rstrip("/\\") + "/tx_payload_manifest.tsv"
        self.raw = b""
        self.rows = {}   # seq -> row dict
        self._load()

    def _load(self):
        raw, lines = _read_lines(self.path)
        self.raw = raw
        header = None
        expect_seq = 0
        for line in lines:
            if line == "":
                continue
            f = line.split("\t")
            if header is None:
                header = f
                if header != TX_PAYLOAD_MANIFEST_HEADER:
                    raise ManifestError(
                        "pilot1 tx_payload_manifest.tsv header mismatch: got %r" % (header,))
                continue
            if len(f) != TX_PAYLOAD_MANIFEST_FIELD_COUNT:
                raise ManifestError(
                    "pilot1 tx_payload_manifest.tsv row has %d fields (want %d): %s"
                    % (len(f), TX_PAYLOAD_MANIFEST_FIELD_COUNT, line))
            seq = int(f[0])
            if seq != expect_seq:
                raise ManifestError(
                    "pilot1 tx_payload_manifest.tsv seq not contiguous (want %d, got %d)"
                    % (expect_seq, seq))
            expect_seq += 1
            source_id = f[2]
            file_name = f[3]            # tx_payload_file == source_id + ".i16"
            quantized_sha256 = f[4]     # tx_payload_sha256 == SHA of the .i16 bytes
            if len(quantized_sha256) != 64:
                raise ManifestError(
                    "pilot1 tx_payload_manifest.tsv tx_payload_sha256 not 64-hex: %s" % line)
            if file_name != source_id + ".i16":
                raise ManifestError(
                    "pilot1 tx_payload_manifest.tsv tx_payload_file != source_id + '.i16': %s"
                    % line)
            row = {
                "source_index": seq,    # the value the board sends over the wire
                "file_name": file_name,
                "complex_count": RF_PAYLOAD_COMPLEX,
                "quantized_sha256": quantized_sha256,
                "session_id": f[1],
                "source_id": source_id,
            }
            self.rows[seq] = row
        if header is None or not self.rows:
            raise ManifestError("pilot1 tx_payload_manifest.tsv empty")

    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()

    def lookup(self, seq):
        if seq not in self.rows:
            raise ManifestError(
                "pilot1 tx_payload_manifest.tsv: seq %d not found" % seq)
        return self.rows[seq]


def run_self_test():
    """Pure-stdlib self-test (no iio, no device).  Writes a synthetic 3-col identity +
    5-col payload manifest pair to a temp dir and exercises load + identity + fail-closed
    paths."""
    import os
    import tempfile

    checks = []

    def check(name, ok, detail=""):
        checks.append(ok)
        print("SELF-TEST %-46s %s%s"
              % (name, "PASS" if ok else "FAIL", (" -- " + detail) if detail else ""))

    def ident_line(session_id, source_id, sha):
        return "\t".join([session_id, source_id, sha])

    def payload_line(seq, session_id, source_id, sha):
        return "\t".join([str(seq), session_id, source_id, source_id + ".i16", sha])

    tmp = tempfile.mkdtemp(prefix="pilot1_tx_manifest_test_")

    def write_ident(body):
        with open(os.path.join(tmp, "tx_manifest.tsv"), "w", encoding="utf-8") as f:
            f.write("\t".join(TX_MANIFEST_HEADER) + "\n")
            f.write(body)

    def write_payload(body):
        with open(os.path.join(tmp, "tx_payload_manifest.tsv"), "w", encoding="utf-8") as f:
            f.write("\t".join(TX_PAYLOAD_MANIFEST_HEADER) + "\n")
            f.write(body)

    try:
        sha_a = "a" * 64
        sha_b = "b" * 64
        id_body = (ident_line("S1", "s1_c00_i00", sha_a) + "\n"
                   + ident_line("S1", "s1_c01_i00", sha_b) + "\n")
        pl_body = (payload_line(0, "S1", "s1_c00_i00", sha_a) + "\n"
                   + payload_line(1, "S1", "s1_c01_i00", sha_b) + "\n")

        # happy path: identity (3-col) + payload (5-col, keyed by seq)
        write_ident(id_body)
        write_payload(pl_body)
        im = Pilot1IdentityManifest(tmp)
        pm = Pilot1PayloadManifest(tmp)
        check("identity loads 2 rows", len(im.rows) == 2, "rows=%d" % len(im.rows))
        check("identity sha256 is 64-hex", len(im.sha256()) == 64, im.sha256())
        check("payload loads 2 rows", len(pm.rows) == 2, "rows=%d" % len(pm.rows))
        check("payload lookup by seq",
              pm.lookup(0)["file_name"] == "s1_c00_i00.i16"
              and pm.lookup(0)["quantized_sha256"] == sha_a
              and pm.lookup(0)["complex_count"] == RF_PAYLOAD_COMPLEX
              and pm.lookup(1)["source_id"] == "s1_c01_i00")
        check("payload source_index == seq",
              pm.lookup(0)["source_index"] == 0 and pm.lookup(1)["source_index"] == 1)

        # fail-closed: identity wrong column count (drop last field -> 2 cols)
        write_ident(id_body.splitlines()[0].rsplit("\t", 1)[0] + "\n")
        try:
            Pilot1IdentityManifest(tmp)
            check("identity wrong field count fails closed", False, "no raise")
        except ManifestError as e:
            check("identity wrong field count fails closed", True, str(e)[:60])

        # fail-closed: payload seq not contiguous (0, 2)
        write_ident(id_body)
        write_payload(payload_line(0, "S1", "s1_c00_i00", sha_a) + "\n"
                      + payload_line(2, "S1", "s1_c01_i00", sha_b) + "\n")
        try:
            Pilot1PayloadManifest(tmp)
            check("payload non-contiguous seq fails closed", False, "no raise")
        except ManifestError as e:
            check("payload non-contiguous seq fails closed", True, str(e)[:60])

        # fail-closed: payload tx_payload_file != source_id + ".i16"
        write_payload("\t".join(["0", "S1", "s1_c00_i00", "WRONG.i16", sha_a]) + "\n")
        try:
            Pilot1PayloadManifest(tmp)
            check("payload wrong file_name fails closed", False, "no raise")
        except ManifestError as e:
            check("payload wrong file_name fails closed", True, str(e)[:60])

        # fail-closed: missing seq lookup
        write_payload(pl_body)
        try:
            Pilot1PayloadManifest(tmp).lookup(999999)
            check("missing seq lookup fails closed", False, "no raise")
        except ManifestError as e:
            check("missing seq lookup fails closed", True, str(e)[:60])

        # fail-closed: empty manifests
        write_ident("")
        write_payload("")
        try:
            Pilot1IdentityManifest(tmp)
            check("empty identity manifest fails closed", False, "no raise")
        except ManifestError as e:
            check("empty identity manifest fails closed", True, str(e)[:60])
        try:
            Pilot1PayloadManifest(tmp)
            check("empty payload manifest fails closed", False, "no raise")
        except ManifestError as e:
            check("empty payload manifest fails closed", True, str(e)[:60])
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    all_ok = all(checks)
    print("pilot1_tx_manifest SELF-TEST %s (%d/%d)"
          % ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(run_self_test())
