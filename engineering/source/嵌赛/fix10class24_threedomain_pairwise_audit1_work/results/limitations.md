# Limitations — fix10class24-threedomain-pairwise-audit1

1. **A-domain sampling**: A is sampled deterministically (seed 20261019) at SNR>=20 from the full HDF5, 400 frames/class; it is NOT the frozen test split and NOT a full-population census.
2. **B_d2 is single-frame/class** (the k=0 holdout), so B_source<->B_d2 is a 24-pair matched measurement, not a distribution.
3. **C coverage is uneven**: 58 recovered tensors across rounds; rms2048 (round 2) has NO recovered-tensor dump on disk, and gated-pass samples have no recovered tensor by construction (classified on-board). C therefore over-represents gated-rejected frames.
4. **snr_db = nan** in the manifest is NOT interpreted as a definite SNR.
5. **No board/SDR/re-capture/training** was performed; C tensors are the saved forced-export model_input files (read-only).
6. **full24 C uses wide_linear_model_input_f32le.bin**; its forced_recovery.json `classification_chain` block reports the SCALAR-chain tensor metrics, so the WL tensor metrics are recomputed here rather than read from that block.
7. The **A<->C** and **B_d2<->C** comparisons are distribution-level / matched sample-level respectively and are limited by C sample counts per class.
