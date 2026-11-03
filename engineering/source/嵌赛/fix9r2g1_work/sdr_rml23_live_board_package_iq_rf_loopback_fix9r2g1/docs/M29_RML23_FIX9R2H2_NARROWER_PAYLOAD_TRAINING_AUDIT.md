# fix9r2h2 narrower payload-domain training block

## Scope

The 46-sample fix9r2h1 board run classified every admitted sample correctly, but
the fixed 0.10 payload-training residual gate excluded two captures at 0.100805
and 0.100978; a third capture was at 0.097818.  Repeating one excluded sample
produced 0.065667 and 0.063893, proving that the classifier and scale recovery
were sound while the pilot lacked RF margin at the unchanged gate.

## Minimal change

`kPayloadTrainingSamplesPerSymbol` changes from 32 to 64.  The deterministic
training block remains 1024 complex samples at the same absolute frame offset,
component RMS, int16 quantization, seed, buffer, sample rate, and RF path.  It now
contains 16 rectangular 16QAM symbols instead of 32, reducing symbol transitions
from 31 to 15 and the nominal symbol rate from 80 ksym/s to 40 ksym/s.

No model, label, preprocessing, synchronization, payload scaling, frame length,
payload offset, fidelity threshold, clip threshold, or fix10 code changes.

## Acceptance

Run the existing two-sample R8 smoke test first.  Only if it reports two valid
estimates, two scored samples, zero exclusions, and 2/2 frozen-baseline agreement
should the unchanged 46-sample regression be run.  Formal acceptance still
requires scored=46, rf_excluded=0, and prediction_agreement=1.0.
