# Procise Lite running-light project

This directory is a copy of `F:\Project\led` with only the copied project
modified. The original project is unchanged.

Open `led.fpe` in Procise. The copied project retains the original target:

- Family: `fmk`
- Device: `fmk230t8`
- Package: `ffg676`
- Speed: `-2`

This target information was inherited from the user's working LED project; it
was not invented or changed here. Before generating a programming file, check
that Procise shows the target expected by the board/vendor flow.

The project contains:

- `sources/led.v`: synthesis top `led`
- `constraints/constrs_1/led.fdc`: Lite LED pins J1/M6/H7/J8
- `rundir/simulation/led_tb.v`: behavioral testbench

Expected board sequence: PL_LED1 -> PL_LED2 -> PL_LED3 -> PL_LED4 -> repeat.

Run these stages in Procise:

1. Open `led.fpe` and confirm the device/package.
2. Load/elaborate the design and confirm `led` is the top module.
3. Run behavioral simulation if desired.
4. Run synthesis, place-and-route, timing and DRC.
5. Generate the programming file only when there are no device/pin errors.
6. Program through the board's PL JTAG connection.

If `BOOTUPE2` is unresolved or a listed package pin is rejected, stop. That is
a project/device configuration problem, not evidence that the board is faulty.
