# PS→PL control smoke hardware validation

- Validation date: 2026-09-29
- Board: FMQL30TAI Lite
- Programming method: temporary PL JTAG programming only
- QSPI/SD programming: not performed
- Bitstream: `ps_pl_ctrl_smoke_top_disable_icap.bit`
- Bitstream SHA-256: `19A6BD2ED8400714E5A29DE41078E851C6CDDD90CFF8702A28F9C36E77B2F7DA`
- Linux test source SHA-256: `8FDFAFC76AA4D53A4C5A712D3297890A9B4F4BD21B2235AB6B008C7F017CBE0D`
- Board executable SHA-256: `C2A74A48B8A87F7756EA5974D5A9F57AE202CB60B1E00A6DC28BC46784750327`
- iCraft packages: `icraft 3.39.0`, `icraftmdzthirdparty 0.1.1`
- Compiler: GCC 9.4.0, `-std=gnu++17`

## FPGA configuration status

- DONE_PIN = 1
- DONE_INTERNAL = 1
- EOS = 1
- GWE = 1
- CRC_ERROR = 0
- IDCODE_ERROR = 0

## First run

```text
VERSION=0x20260927
SCRATCH=0x12345678
STATUS=0x2 RUN_COUNT_BEFORE=0 RUN_COUNT_AFTER=1
PS_PL_CTRL_SMOKE_LINUX_PASS
PROGRAM_RC=0
```

## Reproducibility run

```text
VERSION=0x20260927
SCRATCH=0x12345678
STATUS=0x2 RUN_COUNT_BEFORE=1 RUN_COUNT_AFTER=2
PS_PL_CTRL_SMOKE_LINUX_PASS
PROGRAM_RC=0
```

## Result

The minimum Linux/PS → PL control path is verified on real hardware:

1. Linux reads the PL VERSION register correctly.
2. Linux writes and reads back SCRATCH without mismatch.
3. Linux writes START and observes DONE with BUSY cleared.
4. RUN_COUNT increments exactly once per run.
5. The complete test passed twice consecutively.

## Build issue resolved during validation

iCraft 3.39 uses the GNU `, ##__VA_ARGS__` extension in its public logging macros.
Strict `-std=c++17` leaves an invalid trailing comma for empty variadic arguments.
The official-compatible compilation mode for this test is `-std=gnu++17`.
This was a host-program compilation issue and did not indicate an FPGA, SD-card,
serial-port, or board hardware failure.
