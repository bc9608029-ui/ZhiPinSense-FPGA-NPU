# SAFETY_GATE.md — hard gates before any board operation

These gates **must all pass** before the first board connection, download, or
power-up. They are ordered; do not proceed past a failed gate.

## G0 — asset integrity (before anything)

- [ ] The colorbar bitstream was built from **this package's** XDC
      (`fpga/constrs/hdmi_colorbar_720p.xdc`), whose pins were copied verbatim
      from the official 悟净 demo XDC. **No other board's bitstream is used.**
- [ ] The bitstream TOP is `hdmi_colorbar_720p_top` and PART is
      `xc7z030ffg676-2` (== FMQL30TAI676H). Confirmed in `reports/build_summary.txt`.
- [ ] `reports/timing_gate.txt` shows WNS ≥ 0 and WHS ≥ 0.
- [ ] The bitstream is the Procise `*_disable_icap.bit`, not the raw `.bit`.

## G1 — hardware state

- [ ] Power supply is the correct rail for 悟净; board is on an insulating mat.
- [ ] HDMI cable, JTAG cable, and (later) USB touch cable are the **correct**
      connectors: **HDMI OUT** is the HDMI connector; **PS UART** is the mini-USB
      UART; **PL JTAG** is U19, **PS JTAG** is U18; **USB HOST** is the 4× Type-A
      — do not confuse any of these.
- [ ] No sign of prior damage (bulging caps, burn marks, loose heatsinks).

## G2 — first load must be temporary

- [ ] First test uses a **recoverable temporary load only** (JTAG download to
      the device), **never** automatic writing to QSPI/SD permanent storage.
- [ ] Permanent programming happens only after the temporary test passes and the
      user explicitly confirms it in a later round.

## G3 — during power-up (immediate power-off trigger)

**If ANY of the following appears, cut power immediately:**
- 发热 (heat), 焦味 (burning smell), 异常电流 (abnormal current), or
  线缆发烫 (hot cables).

## G4 — each stage must pass before the next

1. `00_host_verify` — host toolchain + assets present.
2. `01_program_hdmi_test` (temp load) → `02_verify_colorbar` — colour bar visible.
3. `03_boot_linux_verify` — Linux boots, no fbdev/DRM (expected).
4. `04_verify_touch` — USB touch (if any hardware) enumerates.
5. `05_run_ui_mock` — UI mock renders offscreen → HDMI.
6. `07_restore_or_recover` — rollback to official BOOT.bin whenever needed.

**This round is STOPPED at the package boundary:** no board has been connected,
flashed, or powered. Nothing here authorises board work; it only records the
gates that will gate it.
