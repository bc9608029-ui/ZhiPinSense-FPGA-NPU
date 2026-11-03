# Hardware Abstraction Boundary

## Ingress

The portable core accepts `clk`, active-low synchronous-domain reset release,
and ready/valid IQ transactions containing signed int16 I, signed int16 Q and an
error bit. It has no USB, Ethernet, SDR, DDR or AXI ports.

A future adapter must provide:

```text
memory/radio source -> elastic FIFO -> {I,Q,error,valid,ready,drop_event}
```

`drop_event` is an explicit fact from that adapter, not inferred from `ready=0`.
This allows the same core to consume a PS-DDR replay reader, an AXI-stream-like
source, or a later direct digital RF interface without altering feature math.

## Egress

`tensor_buffer_write_if.sv` documents the abstract transaction. The current
packer provides buffer ID, frame ID, logical sample index, five byte addresses,
five INT8 values, start/done/error and IRQ. `buffer_release[1:0]` transfers
ownership back from software/NPU to the producer.

`buffer_transfer_if.sv` separately defines a generic request handshake with
byte `buffer_address`, byte `buffer_length`, buffer/frame identity, completion,
error and IRQ. It is an adapter contract only and implies no DMA vendor IP.

The future board adapter is responsible for:

- converting logical writes to BRAM writes or coalesced DDR bursts;
- mapping physical addresses and cache coherency;
- connecting a confirmed DMA/equivalent engine;
- translating completion/error to confirmed interrupt facilities;
- exposing calibration/control registers on a confirmed control bus.

No AXI DMA instance, descriptor format, DDR address, or interrupt number is
defined here because Procise IP/BSP capabilities have not been verified.

## Clock and reset boundary

All present modules use one abstract `clk` and active-low `rst_n`. Board-level
PLL selection, input frequency, reset synchronization and clock-domain crossing
are postponed. Each asynchronous or differently clocked ingress/egress must be
wrapped by a board adapter with a reset synchronizer and verified CDC FIFO.
There is no specific pin, clock frequency, or timing constraint in this tree.
