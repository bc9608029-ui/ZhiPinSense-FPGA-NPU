# Wujing Lite running-light board check

This is an isolated PL running-light test for the Wujing Lite board. It does
not modify `F:\Project\led` or the RF cognitive-system project.

## Confirmed board mapping

The Wujing Lite hardware manual identifies the target as
`JFMQL30TAI676H` and gives these PL LED package pins:

| Signal | Package pin | RTL bit |
|---|---:|---:|
| PL_LED1 | J1 | `led[0]` |
| PL_LED2 | M6 | `led[1]` |
| PL_LED3 | H7 | `led[2]` |
| PL_LED4 | J8 | `led[3]` |

The schematic drives each LED through an NDS331N MOSFET, so the RTL uses
active-high LED outputs.

## Why no external clock pin is used

The Lite manual shows a `PL_100MHz` clock network but does not state its BGA
package pin. Guessing that pin would make a failed test ambiguous. This design
instead uses `BOOTUPE2.CFGMCLK`, a primitive present in the installed Procise
FMZ7/FMK7 device libraries. The blink rate is deliberately approximate and is
not a precision timing result.

## Procise steps

1. Create a new RTL project in Procise.
2. Select the actual board device `JFMQL30TAI676H`, package `676`, speed `-2`
   (use the exact names shown by the installed Procise device selector).
3. Add only `rtl/lite_led_flow.v` to the synthesis/design source set.
4. Set `lite_led_flow` as the top module.
5. Add `constraints/lite_led_flow.fdc` as the design constraint file.
6. Do **not** add `tb/bootupe2_sim.v` to synthesis; it is simulation-only.
7. Run elaborate, synthesis, place-and-route and timing/DRC checks.
8. Generate the programming file only if there are no device, pin, or DRC
   errors, then program via the board's PL JTAG connection.

Expected board behavior: one of the four PL LEDs is on at a time, moving in
the order LED1 -> LED2 -> LED3 -> LED4 -> LED1.

## PASS/FAIL meaning

- PASS: the programming flow completes and the four LEDs circulate in order.
- If synthesis reports `BOOTUPE2` unresolved, stop and use the vendor-selected
  primitive/library for the chosen JFMQL30TAI676H project; do not treat that as
  a board failure.
- If placement rejects a listed LED pin, stop and re-check the selected device
  and package; do not force placement to a different pin.
- A programming failure alone does not identify a defective board; first check
  JTAG mode, cable, power, and the selected target device.
