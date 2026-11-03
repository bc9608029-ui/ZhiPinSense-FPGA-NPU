# RML24 UI polish1 scope

This work tree is an independent copy of `constellation_ui_desktop1_work`.
The verified source tree is not modified.

## Changes in scope

- RML24 product naming and clearer visual hierarchy.
- Responsive wide/compact layout.
- More legible result, link-metric, and data-integrity grouping.
- Consistent dark engineering palette while preserving the four stage colors.
- Translation-safe `%1` placeholders in touched UI strings.

## Explicitly out of scope

- No SDR, model, DSP, synchronization, recovery, threshold, or protocol changes.
- No claim of live input: `FileIqFrameSource` remains the only implemented source.
- No claim that band scan is implemented in the final RML24 runtime.
- No changes to board packages or previously verified delivery trees.
