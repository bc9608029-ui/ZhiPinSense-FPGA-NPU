import QtQuick 2.15

// Theme.qml — single source of truth for the offline viewer's colors/sizes.
// Instantiated once in Main.qml and passed down to child components (a plain
// QtObject, so no singleton/module machinery is required at runtime).
QtObject {
    // Surfaces
    readonly property color background: "#14161A"
    readonly property color panelBackground: "#1D2026"
    readonly property color plotBackground: "#0E1013"
    readonly property color border: "#2A2F3A"
    readonly property color gridLine: "#232833"
    readonly property color axisLine: "#3A4152"

    // Text
    readonly property color textPrimary: "#E6E8EC"
    readonly property color textSecondary: "#9AA3B2"
    readonly property color textFaint: "#6B7484"
    readonly property color accent: "#3DDC84"
    readonly property color danger: "#E5605F"
    readonly property color warning: "#E8C93C"
    readonly property color offlineBadge: "#E8C93C"

    // Stage colors (must match the C++ renderer; color is never the only cue —
    // the stage text and legend are always shown too).
    readonly property color rawRx: "#D0D4D8"
    readonly property color recoveredPayload: "#22C3E6"
    readonly property color modelInput: "#3DDC84"
    readonly property color symbolSampled: "#E8C93C"
    readonly property color outlier: "#E5605F"

    // Metrics
    readonly property int radius: 6
    readonly property int gap: 8
    readonly property int fontSizeSmall: 11
    readonly property int fontSizeNormal: 13
    readonly property int fontSizeLarge: 16
}
