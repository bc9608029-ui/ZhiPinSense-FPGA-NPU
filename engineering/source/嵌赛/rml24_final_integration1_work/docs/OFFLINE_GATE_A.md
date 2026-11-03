# Offline Gate A

## Acceptance criteria

1. The production recovery source is byte-for-byte identical to the validated
   `candidate_two_dc.py`.
2. The frozen model JSON/raw SHA-256 values match the recorded identities.
3. Development and validation source hashes are disjoint.
4. Both validation rounds contain the complete 240-frame denominator.
5. Independently recomputed results are R1 233/240 and R2 230/240 for the
   candidate, with zero receiver failure and zero baseline-correct regression.
6. The two RF rounds have distinct recovered input hashes for all 240 matching
   sequence positions.
7. After raw captures are copied to the PC, all 480 raw-to-tensor SHA values
   reproduce the board evidence.

Criteria 1-6 are computer-verifiable with the current files.  Criterion 7 is
pending because the two raw capture directories remain on the board.

## Why this gate exists

The final receiver imports the frozen recovery module rather than rewriting it.
That makes integration failures observable: a changed tensor SHA identifies an
input, recovery, dtype, layout, or numerical-environment difference before UI
or live scheduling is added.

## Prohibited claims before criterion 7

- Do not claim 480/480 byte-exact raw replay on the PC.
- Do not claim the final live entry has passed RF validation.
- Do not claim arbitrary no-preamble or arbitrary-transmitter recognition.

