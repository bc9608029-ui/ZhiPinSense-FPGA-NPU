pragma Singleton
import QtQuick 2.15

// Central token set for the embedded (software-rendered) HDMI panel at 1024x600.
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

    // Status. Never the sole carrier of state — each is paired with a shape
    // glyph (statusGlyph) and a text label in the UI.
    readonly property color ok:           "#2fd37f"
    readonly property color warning:      "#f0b429"
    readonly property color error:        "#f05545"
    readonly property color disconnected: "#6f7d8c"
    readonly property color unknown:      "#6f7d8c"

    // MOCK badge: prominent, clearly-not-real-RF. Distinct hue from the status
    // colours so a "MOCK" label is never mistaken for a warning/error.
    readonly property color mock:      "#c9813a"
    readonly property color mockText:  "#1a1208"

    function statusColor(name) {
        switch (name) {
        case "ok":     case "normal": return ok
        case "warning":              return warning
        case "stale":                return warning
        case "error":                return error
        case "disconnected":         return disconnected
        default:                     return unknown
        }
    }

    // Shape glyph paired with each state so colour-blind users (and a monochrome
    // capture) can still tell states apart: ● ok, ▲ warning/stale, ■ error,
    // ◆ disconnected, ◇ unknown.
    function statusGlyph(name) {
        switch (name) {
        case "ok":     case "normal": return "●"  // ●
        case "warning":              return "▲"  // ▲
        case "stale":                return "▲"  // ▲
        case "error":                return "■"  // ■
        case "disconnected":         return "◆"  // ◆
        default:                     return "◇"  // ◇
        }
    }

    // Type scale (pixel sizes — embedded fonts are fixed at build time).
    readonly property int display: 44
    readonly property int h1:      20
    readonly property int body:    17
    readonly property int caption: 14
    readonly property int small:   13

    // Spacing and touch targets (touch >= 48 px per spec).
    readonly property int touch:  48
    readonly property int gap:    12
    readonly property int gapSm:  8
    readonly property int radius: 6
}
