# Bandwidth adaptation feasibility
Offline diagnostic only; no board/RF change.
Current public random-QPSK training occupies much of the 2.56MS/s sampled band even for narrow payloads. Selecting an analog filter based only on recovered payload bandwidth can remove necessary public training and break synchronization.
Separate whole-frame and payload spectra. This heuristic is not a calibrated occupied-bandwidth measurement and is sensitive to noise floors/AM carriers.
Immediate priority: finish24-class AGC/repeat validation. Then compare3/5/10/18MHz receive filters with public recovery and fixed failure denominators. Do not expose arbitrary sample rates or shrink filters below public-training requirements based on this estimator alone.
Current acquisition cannot discover signals wider than its2.56MS/s instantaneous sampled band. LO tuning range70..6000MHz is unrelated to instantaneous bandwidth.
