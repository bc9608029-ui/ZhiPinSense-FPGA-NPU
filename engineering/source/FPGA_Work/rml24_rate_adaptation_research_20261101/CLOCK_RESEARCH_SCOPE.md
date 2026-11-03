# Timing adaptation research update

This is isolated PC-only development. No board configuration, formal candidate, model, waveform set or active formal helper was changed.

- Three discrete logical timing scales with four repeat counts: 12/12 synthetic recoveries in the original zero-clock-drift test. This is not RF or classification validation.
- Without clock correction, offsets -100,-50,+50,+100 ppm were all rejected; zero offset recovered.
- A matching 50 ppm compensation grid recovered the five development cases, but all four halfway-grid offsets (-75,-25,+25,+75 ppm) were rejected. The first result therefore does not establish continuous timing adaptation.
- A finer 5 ppm grid is being evaluated separately on non-grid offsets. Estimated ppm is only a search hypothesis, not a calibrated hardware clock measurement. Do not expose it as a measured parameter.
- Pure Gaussian noise: 0 accepted out of 12 tests. This small synthetic test does not establish an operational false-alarm rate; expanded hypothesis search needs its own noise test.

Next gates: independent offsets, wider CFO and gain coverage, noise rejection for the expanded search, actual raw RF recovery, then unchanged-model classification. Keep sustained cyclic transmission distinct from isolated bursts. No promotion or deployment is authorized by these synthetic results.

Latest development result: 5 ppm grid recovered all four non-grid offsets (-73,-23,+27,+77 ppm), payload relative errors [0.1105, 0.0421, 0.0502, 0.0997]. Expanded grid accepted no candidates in six pure-noise captures. Estimated ppm values can differ substantially from injected ppm: this is a recovery search, not an accurate clock estimator. No RF or classification validation.
