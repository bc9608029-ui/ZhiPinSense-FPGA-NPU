# Procise FFT IP adapter contract

Do not replace the vendor FFT with a Python model or an empty RTL shell.

The generated core must implement a 1024-point forward complex FFT with signed
16-bit I/Q input, unscaled signed 27-bit real/imaginary output, natural bin
order 0..1023, and an explicit output index. Input and output use valid/ready
and a last marker. Reset, rounding, overflow, latency, and continuous-frame
behavior must be frozen in the generated-IP identity record.

`procise_fft_axis_boundary.sv` adapts this interface without changing values.
`fft_psd_stream_writer.sv` computes unsigned-54-bit magnitude square, maps
natural bin addresses into fftshift storage order, and toggles the external
ping-pong bank only after a complete frame.

If the migrated XFFT cannot provide this exact unscaled 27-bit contract, stop and
revise the Golden and all vector identities explicitly. Silent truncation,
implicit block scaling, or an undocumented bit-reversed order is forbidden.

First build the modules as an independent/OOC project. Do not overwrite the
working display/NPU bitstream until synthesis, P&R, STA, same-IQ A/B, automatic
fallback, and RF regression have passed.
