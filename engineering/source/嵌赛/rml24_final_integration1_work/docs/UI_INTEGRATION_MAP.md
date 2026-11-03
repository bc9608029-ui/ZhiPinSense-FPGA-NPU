# Final UI integration map

## Reuse

Reuse these tested components from `fix10class24_waterfall1_work`:

- `ui_sw/direct_framebuffer_backend.*`: FPGA HDMI framebuffer submission.
- `ui_sw/font_atlas*`, `ui_theme.hpp`, `ui_layout.hpp`: embedded drawing assets.
- `ui_sw/waterfall_history.hpp`, `waterfall_render.*`: 256-bin waterfall history.
- `board_package/unix_socket_server.hpp`: local JSONL transport.
- `board_package/touch_evdev.hpp`: touch input.

The desktop constellation implementation in `ui_constellation_polish1_work` is
a visual/reference prototype only. Its offline file loader is not a board live
input and must not enter the production runtime.

## Replace/adapt

Do not use `result_frame_rml23_parse.hpp` or `map_to_state_rml23()` for the final
system. They enforce 23 merged classes and would change the required 24-class
result space. The final input is `rml24-final-ui-v1` from
`contract/ui_event_v1.schema.json`.

The board adapter must:

1. fail closed on schema, version, or class-count mismatch;
2. map all 24 probabilities without AM-SSB merging;
3. clear the displayed class on `RECOVERY_FAILED` or `NO_SIGNAL`;
4. update constellation only when `iq_valid=true`;
5. update waterfall only when `spectrum_valid=true`;
6. mark retained visuals stale rather than presenting them as current;
7. never consume `self_test` truth in normal operation.

The canonical producer, payload generation and framebuffer overlay are now
implemented and host tested. The overlay keeps the raw 24-class contract,
renders a relative-to-frame-peak spectrum/waterfall, and renders 256 recovered
IQ points on the third page. A clean assembled copy of the validated waterfall
tree passes a full x86_64 C++ link build.

This remains `READY_FOR_STAGE7_BOARD_INTEGRATION`, not an HDMI or aarch64 pass:
the actual board build, framebuffer output, touch page switching and live socket
traffic still require the board and screen.
