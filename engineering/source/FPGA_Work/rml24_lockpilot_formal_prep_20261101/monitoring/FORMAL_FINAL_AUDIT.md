# Gain-freeze formal RF audit

No automatic deployment performed.

- fixed240: 239/240; missing 0; gate True
- search240: 237/240; missing 0; gate True
- sweep24: 23/24; missing 0; gate False
- wide13: 13/13; missing 0; gate True

All four accuracy gates passed: False
Controller ended before completion: False

These are fresh RF acquisitions of the existing frozen waveforms, not unseen-waveform generalization. Wide13 uses coordinated fixed-frequency RX/TX, not blind whole-band discovery.
If any gate failed, do not promote. Preserve baseline and inspect failures. Synthetic timing research is excluded from formal results.