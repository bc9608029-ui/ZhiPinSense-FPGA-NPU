pragma Singleton
import QtQuick 2.15

// Central token set for the embedded (software-rendered) HDMI panel.
// Flat solid fills only — no gradients, shadows, or blur, so it stays cheap on
// the Zynq-7030 PS which has no GPU.
QtObject {
    // Surfaces.
    readonly property color background:  "#0f141a"
    readonly property color panel:       "#1a222b"
    readonly property color panelAlt:    "#232e39"
    readonly property color border:      "#2e3b48"
    readonly property color text:        "#e9eff5"
    readonly property color textDim:     "#93a4b3"
    readonly property color accent:      "#3fa2f7"

    // Status. Never the sole carrier of state — each is paired with a shape and a
    // text label in the UI.
    readonly property color ok:           "#2fd37f"
    readonly property color warning:      "#f0b429"
    readonly property color error:        "#f05545"
    readonly property color disconnected: "#6f7d8c"
    readonly property color unknown:      "#6f7d8c"

    function statusColor(name) {
        switch (name) {
        case "ok":           return ok
        case "warning":      return warning
        case "error":        return error
        case "disconnected": return disconnected
        default:             return unknown
        }
    }

    // Type scale (pixel sizes — embedded fonts are fixed at build time).
    readonly property int display: 72
    readonly property int h1:      26
    readonly property int body:    20
    readonly property int caption: 16
    readonly property int small:   13

    // Spacing and touch targets.
    readonly property int touch:  48
    readonly property int gap:    16
    readonly property int gapSm:  8
    readonly property int radius: 6
}
