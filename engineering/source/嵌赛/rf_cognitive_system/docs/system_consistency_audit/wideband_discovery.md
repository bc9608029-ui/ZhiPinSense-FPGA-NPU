# Wideband signal-discovery golden architecture

The existing optional FFT monitor is only a visualization/energy path. A
wideband cognitive receiver needs a separate discovery and channel-extraction
main chain:

```mermaid
flowchart LR
    IQ[Wideband IQ] --> CH[overlap framing + window]
    CH --> FFT[FFT or PFB channelizer]
    FFT --> PS[power spectrum / temporal averaging]
    PS --> NF[noise-floor estimation]
    NF --> DET[threshold / CFAR-like detection]
    DET --> MERGE[contiguous-bin merging]
    MERGE --> EST[signal count + center/BW/power/SNR]
    EST --> JOB[CPU candidate table / priority queue]
    JOB --> DDC[per-signal NCO/DDC]
    DDC --> LPF[low-pass + decimation/resampling]
    LPF --> FRAME[128 ksample/s, 1024-point AMR frame]
    FRAME --> FEAT[Power/Lag-1]
    FEAT --> QUEUE[NPU AMR queue]
```

## Golden processing definition

The initial Python reference uses overlapping Hann-window FFT frames, averaged
power, a robust lower-spectrum noise estimate, a dB threshold, gap-tolerant
contiguous-bin merging and power-weighted center frequency. For every detected
region it reports:

- first/last FFT bin;
- center-frequency offset;
- occupied-bandwidth estimate;
- integrated excess power;
- estimated SNR;
- frame/timestamp association.

The reference then performs complex frequency shift, FIR low-pass and rational
resampling to an AMR frame. This implementation is a functional golden model,
not a final CFAR/PFB algorithm or hardware claim.

## Single-signal mode

If RF tuning and bandwidth already guarantee one centered signal, discovery can
be bypassed: validate energy, take one 1024-point frame and enqueue AMR. If the
signal is not centered or the input sample rate is wider than 128 ksample/s,
retain one DDC/LPF/decimator job before AMR. Thus single-signal mode is a
one-candidate degeneration of the same architecture.

## Multi-signal mode

Each merged detection creates a descriptor containing frame ID, center offset,
bandwidth, estimated SNR/power and DDC parameters. FPGA executes one or more
DDC/filter/decimator contexts; CPU schedules candidates by power, bandwidth or
region of interest and submits completed fixed-shape tensors to the NPU queue.
Backpressure policy must define whether excess candidates are deferred or
dropped and increment a visible counter.

DDC is required whenever a candidate is away from DC. Low-pass filtering is
required to reject adjacent detections before decimation. Decimation/resampling
is required when wideband input Fs differs from the model's frozen 128 ksample/s.
The current model was trained at symbol rate 16 ksymbol/s and 8 samples/symbol;
arbitrary real signals therefore also require symbol-rate estimation or a bank
of resampling hypotheses. This is a major unresolved system constraint.

## Hardware/software partition

Best suited to FPGA:

- sample framing/windowing, FFT/PFB and power;
- streaming averaging/noise statistics;
- thresholding, bin flags and optionally region merging;
- NCO complex mixing, FIR and integer/rational decimation;
- Power/Lag-1 generation, quantization, FIFO and DMA.

Best managed by CPU:

- adaptive threshold policy and scan/tuner control;
- candidate lifecycle, deduplication and prioritization;
- selection of DDC/resampling coefficients;
- NPU queue, result association, logging and UI;
- fallback/recovery policy and long-term spectrum occupancy map.

Region merging may start on CPU for observability, then move to FPGA if traffic
or latency measurements justify it.

## Required tests before RTL

1. Empty/noise-only false-alarm sweeps across noise power.
2. One and multiple tones with known bin/non-bin-centered frequencies.
3. QPSK/QAM/FSK/OFDM signals with known center and occupied bandwidth.
4. Adjacent/overlapping signals, near-far ratios and band-edge wrap cases.
5. Time-varying noise floor, bursts and narrowband interference.
6. Center-frequency and bandwidth error versus FFT/PFB size and averaging.
7. DDC frequency sign, FIR rejection, alias protection and output sample rate.
8. 1024-point AMR frame shape, scaling and metadata continuity.
9. Candidate queue overflow, deterministic ordering and dropped-frame counters.
10. Python→fixed-point→RTL point-by-point regression.

The current executable reference is `dsp/wideband_discovery.py`.
