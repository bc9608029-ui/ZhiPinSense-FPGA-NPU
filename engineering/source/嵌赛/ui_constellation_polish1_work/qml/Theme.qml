import QtQuick 2.15

// Theme.qml — single source of truth for the offline viewer's colors/sizes.
// Instantiated once in Main.qml and passed down to child components (a plain
// QtObject, so no singleton/module machinery is required at runtime).
QtObject {
    // Surfaces
    readonly property color background: "#080E18"
    readonly property color panelBackground: "#101A29"
    readonly property color panelElevated: "#152238"
    readonly property color panelMuted: "#0C1523"
    readonly property color plotBackground: "#070C14"
    readonly property color border: "#263A55"
    readonly property color borderStrong: "#345172"
    readonly property color gridLine: "#17263A"
    readonly property color axisLine: "#3B5878"

    // Text
    readonly property color textPrimary: "#F2F7FC"
    readonly property color textSecondary: "#A9B9CC"
    readonly property color textFaint: "#70839A"
    readonly property color accent: "#3DDC84"
    readonly property color accentBlue: "#45B8FF"
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
    readonly property int radius: 10
    readonly property int gap: 10
    readonly property int fontSizeSmall: 11
    readonly property int fontSizeNormal: 13
    readonly property int fontSizeLarge: 17
    readonly property int fontSizeHero: 30
}
