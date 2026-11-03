# Adaptation research — 2026-11-01
Goal: expand stable recognition operating conditions. Do not pursue fewer conventions at expense of measured reliability.
Formal deployed baseline: range_20261101, fixed2.56MS/s, eight payload repeats, manual35dB,18MHz RF bandwidth. Experimental work has not replaced formal configuration.

## Findings with preserved evidence
- Paired24-class same-source eight-repeat control: manual35dB24/24; continuous slowAGC18/24; fastAGC21/24.
- Gain-settle then freeze paired control: manual24/24 and freeze24/24. Promising, limited to tested profile.
- Freeze, same24classes: single repeat22/24; eight24/24. Single repeat fails17->18 and20->16; not adopted.
- Freeze with eight repeats,3/5/18MHz RX bandwidth: each24/24. Does not mean bandwidth estimated automatically.
- Freeze5MHz TX gain sweep: -60,-50,-40,-30dB each24/24; -70dB0/24, all recovery failures. This is cabled TX setting, not calibrated receiver dBm.
- Weak failed captures had RX gain71dB. Input amplitude normalization alone: weak0/24, controls24/24 each.12 synthetic noise cases0falseaccept.
- Always temporal-combine existing cyclic repeated frames: weak22/24 recovery, but controls20/24 each. Therefore rejected as universal transform.
- Failure-only temporal-combine then frozen-model replay on same development captures: weak22/24 correct; -60/-40dB controls24/24 each. Requires repeated identical temporal frames, adds latency; not applicable without this property.
- New96-item independent RF acquisition using same existing message0 waveforms now RUNNING:24classes x TX gains(-60,-65,-67.5,-70), original-success path preserved, fallback only after recovery failure. Fixed denominators, first capture in predefined window, failures kept. Real post-TX no-signal captures included. This is not unseen-source validation.

## Sampling and bandwidth cautions
Hardware1.28MS/s write rejected under current configuration.2.56 and approx5.12MS/s BPSK5/5 each; digital1.28 resampling BPSK5/5, not hardware1.28 proof. Keep2.56 formal rate.
Public training spectrum spans~2.515MHz despite narrow payloads. Payload bandwidth alone cannot determine safe analog filtering.70..6000MHz tuning span is not simultaneous bandwidth.

## Active evidence
E:/FPGA_Work/rml24_weak_adaptive_rf_20261101: STATUS.json, FROZEN_PLAN.json, SOURCE_FREEZE.json, live TX events, then SCORE.json and ADAPTATION_COVERAGE.json.
E:/FPGA_Work/rml24_weak_recovery_20261101: normalization and combining code plus local selection; full results on board /root/rml24_weak_recovery_20261101 and /root/rml24_weak_adaptive_classification_20261101.
Raw IQ and rejection records retained. No threshold/model changes authorized by successful scores alone. Next decisions require actual fresh-RF and false-accept results.

## Fresh RF candidate result
96 fixed opportunities, same existing message0 waveforms; gains-60/-65/-67.5/-70dB. Original-success recovery then temporal fallback:23/24,24/24,22/24,15/24 respectively. Same selected captures without fallback:23/24,24/24,9/24,0/24.20 post-transmission captures had0falseaccept. Candidate84/96 overall; missing0. No deployment.
Do not substitute development weak22/24 for fresh weak15/24. Improvements depend on repeated identical temporal frames. Offline identity gate passes same-message24/24 but also accepts changed-message AM-DSB-WC; not a proof of message identity. Actual gate evaluation stored on board, not yet incorporated into frozen RF candidate.
Next weak-bandwidth96case comparison started automatically by active agent:3MHz/5MHz,24classes x(-67.5/-70dB) per bandwidth, original and fallback scored separately. Formal system preserved.

## Burst/timing boundary
Gain-freeze prototype consumes3x16384RX samples before classification capture:19.2ms of nominal sample time at2.56MS/s, plusUSB/software latency. Main65536sample capture adds25.6ms. All RF tests so far use cyclic sustained transmission. Payload repeat1 means one1024sample payload in a3.6ms frame, not one-shot transmitter operation. Eight-repeat frame is6.4ms.
Therefore neither gain-freeze nor temporal fallback has demonstrated isolated single-burst acquisition. Do not market reduced intra-frame repeats as eliminating temporal transmission repetition. This is a separate adaptation objective.
