# FPGA–NPU–CPU System Partition

## Data plane

```text
USB/GigE SDR
   |  (PS driver/socket owns transport)
   v
PS receive buffers -> DDR replay ring -> board adapter -> generic IQ stream
                                                        |
             +------------------------------------------+------------------+
             |                                                             |
             v                                                             v
  Advanced wideband path                                      Mandatory core path
  overlap/window -> FFT/PFB                                    frame/FIFO
  -> PSD/noise/detect/merge                                    -> Power/Lag
  -> descriptor -> DDC/FIR/rate change                         -> INT8/pack
             |                                                             |
             +--------------- 1024 complex samples ------------------------+
                                                                           v
                                                              abstract buffer writes
                                                                           v
                                                                    DDR/NPU adapter
                                                                           v
                                                               TimePowerPhase NPU
```

The SDR is not bound to PL. For the first board integration, PS software owns
USB or Ethernet ingress and maintains a DDR replay/ring buffer. A board-specific
adapter will translate memory reads to the RTL's generic ready/valid IQ stream.

## Responsibilities

| Domain | Frozen responsibility for the target system |
|---|---|
| FPGA/PL | Framing, buffering, FFT/PFB spectrum DSP, signal detection, DDC, FIR/rate change, exact Power/Lag, INT8 quantization, tensor packing, status counters |
| NPU | Frozen TimePowerPhase neural inference only |
| CPU/PS | SDR control and transport, candidate management, DDC configuration, buffer ownership, NPU queueing, UI, logs, recovery |

The mandatory core is executable RTL now. The wideband path is an algorithmic
golden architecture now and becomes RTL in verified increments. Neither part
contains a claimed board throughput, utilization, latency, or power result.

## Control plane

CPU-controlled registers will eventually supply calibration multipliers/shifts,
buffer addresses/lengths, frame enables, and wideband candidate parameters.
Status returns `frame_id`, buffer ownership, completion interrupt, sticky frame
error, dropped-input count, and five saturation counts. The register bus and
address map remain outside the portable core until Procise/BSP support is known.
