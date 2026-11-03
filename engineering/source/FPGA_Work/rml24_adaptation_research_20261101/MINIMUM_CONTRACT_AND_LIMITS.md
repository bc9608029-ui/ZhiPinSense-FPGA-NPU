# Remaining assumptions and deployment criteria

Goal: widen accepted TX strength/conditions without degrading the preserved system. No result establishes a globally optimal solution or arbitrary raw-signal recognition.

## Most mature isolated receiver candidate

Gain settle then manual freeze,5MHz RX filter, original2.56MS/s, public8-repeat framing, frozen model, plus centered public-pilot fallback only after an original locked check fails. Integrated nominal search short smoke24/24 with no missing items; clean NPU/FPGA display and restoration passed. Full fresh RF performance-preservation regression is prepared, pending explicit user consent. Required reference scores: fixed235/240, search237/240, sweep24/24, coordinated BPSK frequencies13/13. No automatic deployment.

## Optional TX numerical improvement

Peak-constrained integer-QPSK pilot scaling plus analog attenuation compensation. Uses no class labels. Targeted failures improved;24 existing source0 waveforms51/51 steady-window captures classified correctly. It improves the demonstration transmitter, but must not be required of every external transmitter as a substitute for receiver robustness. Actual RF power matching was not instrument-calibrated. Numeric limits checked for240 payloads and7 nominal gain settings,1680 cases; RF coverage is narrower.

## Repetition reduction

Same unaveraged8-repeat RF captures, firstN recovered segments averaged, then tiled for the frozen model: N1=51/51,N2=50/51,N4=50/51,N8=51/51. This is not shortened-frame RF and has no monotonic accuracy guarantee. Actual single-payload-repeat cyclic RF is a separate running short test; no isolated one-shot burst claim. Gain priming consumes multiple milliseconds and can miss an isolated short burst.

## Assumptions still present

- Known common public head and tail, their relative scale, and compatible frame structure. This is public-framed AMR, not arbitrary blind waveform classification.
- Frozen model24-class definition and1024-complex-sample payload representation. Repeating a recovered mean into8 model inputs adds no independent observations.
- Valid search range, adequate capture bandwidth, sufficient SNR and no clipping. RX gain adaptation cannot recover information below the noise floor.
- The nominal2.56MS/s timing contract remains in deployable candidates. Multi-rate and clock drift recovery are synthetic research only.
- Coordinated13-frequency tests do not show blind70-to6000MHz discovery or all classes/all amplitudes at every frequency.

Preserve per-frame failures, fixed denominators and private TX truth. Never choose a recovery/amplitude using expected labels, drop failing items, lower gates, or merge research claims into formal scores. Model, bitstream and autostart are unchanged.
