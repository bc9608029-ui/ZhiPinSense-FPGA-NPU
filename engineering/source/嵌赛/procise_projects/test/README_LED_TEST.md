# Wujing Lite LED running-light test

Target retained from this Procise project:

- Family: `jfmql`
- Device: `jfmql30tai676h`
- Package: `fcbga676`
- Speed: `-2`

Project contents:

- Top RTL: `sources/test.v`, module `test`
- Constraints: `constraints/constrs_1/test.fdc`
- Testbench: `rundir/simulation/test_tb.v`, module `test_tb`

Expected board behavior:

`PL_LED1 -> PL_LED2 -> PL_LED3 -> PL_LED4 -> repeat`

Open `test.fpe`, reload/elaborate the design, then run synthesis,
place-and-route, timing/DRC and programming-file generation. Do not treat a
tool error as a board failure. If Procise reports an unresolved `BOOTUPE2` or
rejects an LED package pin, stop and check the project/device configuration.
