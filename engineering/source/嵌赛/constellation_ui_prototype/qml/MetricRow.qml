import QtQuick 2.15
import QtQuick.Layouts 1.15

// MetricRow.qml — one labeled metric line (label left, value right). Used by
// MetricsPanel; keeps the metrics panel free of per-field layout boilerplate.
RowLayout {
    spacing: 8

    property string label: ""
    property string value: ""
    property color valueColor: theme ? theme.textPrimary : "#E6E8EC"
    property bool valueBold: false
    property QtObject theme: null

    Text {
        text: label
        color: theme ? theme.textSecondary : "#9AA3B2"
        font.pixelSize: theme ? theme.fontSizeNormal : 13
        Layout.preferredWidth: 92
        Layout.alignment: Qt.AlignVCenter
    }
    Text {
        text: value
        color: valueColor
        font.pixelSize: theme ? theme.fontSizeNormal : 13
        font.bold: valueBold
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignVCenter
        elide: Text.ElideMiddle
    }
}
