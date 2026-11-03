# M29 RML24 UI polish1 audit

## Status

`M29-RML24-UI-POLISH1-SOURCE-READY-FOR-GUI-REGRESSION`

This status means the visual source changes passed static QML validation. It does
not claim target-board runtime integration, live SDR input, sweep support, or a
new desktop screenshot verification.

## Safety and isolation

- Source: `F:\嵌赛\constellation_ui_desktop1_work`
- Independent work tree: `F:\嵌赛\ui_constellation_polish1_work`
- The source tree and every board/model/DSP delivery tree were left unchanged.
- No board, SDR, network service, installer, model, threshold, protocol, or
  recovery code was touched.

## Visual changes

1. Updated visible product naming from RML23 prototype to RML24 signal analysis.
2. Added a deeper navy surface hierarchy without changing the four stage colors.
3. Promoted current class and confidence into a clear hero card.
4. Grouped link metrics separately from data-integrity information.
5. Added responsive behavior: two columns on wide screens, vertical scrolling on
   compact screens, and a horizontally scrollable control strip.
6. Reduced compact-header crowding by hiding secondary file/source information.
7. Replaced touched translatable string concatenations with `%1` placeholders.

## Validation

- `D:\Anaconda\Library\bin\qmllint.exe qml/*.qml`: `RC=0`.
- Changed-source inventory is limited to QML presentation files, application
  branding in `src/main.cpp`, the CMake comment, and this documentation.
- WSL GUI/build regression was not rerun because the local WSL service returned
  `E_ACCESSDENIED`. No permission escalation was requested.

## Known limitations retained deliberately

- `FileIqFrameSource` remains the only implemented source; UI is still offline.
- Legacy QtQuick.Dialogs 1.3 remains and may still emit six cosmetic binding-loop
  warnings. Replacing it safely requires a runtime-supported dialog backend.
- The board framebuffer UI is not replaced by this desktop tool.
- Real RML24 band scan remains a producer/runtime task, not a visual-only change.
- A Qt build plus screenshots at 1280x720, 900x600, and 480x360 are required
  before promoting this status to desktop-verified.
