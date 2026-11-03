import QtQuick 2.15

// LegendDot.qml — a small colored square + label, used in the constellation
// legend. Pure static QML (no per-point objects, no Canvas).
Row {
    spacing: 4

    property color dotColor: "#FFFFFF"
    property string label: ""
    property QtObject theme: null

    Accessible.ignored: true   // decorative legend entry, not an interactive control

    Rectangle {
        width: 10
        height: 10
        radius: 2
        color: dotColor
        anchors.verticalCenter: parent.verticalCenter
    }
    Text {
        text: label
        color: theme ? theme.textSecondary : "#9AA3B2"
        font.pixelSize: theme ? theme.fontSizeSmall : 11
        anchors.verticalCenter: parent.verticalCenter
    }
}
