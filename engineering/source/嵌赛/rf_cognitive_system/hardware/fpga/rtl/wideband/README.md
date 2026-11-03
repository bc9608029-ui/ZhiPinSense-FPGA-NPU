# Advanced wideband RTL status

No wideband RTL is implemented in this stage. The board-independent algorithm
and interface plan is in `../../docs/wideband_architecture.md`; its executable
Python golden reference is `../../python/wideband_reference.py` together with
`../../../../dsp/wideband_discovery.py`.

This empty RTL boundary is deliberate: FFT/PFB, DDC, FIR, and rate-change RTL
must follow bit-width and rate decisions validated by replay data, then be
connected through a separately verified board adapter.
