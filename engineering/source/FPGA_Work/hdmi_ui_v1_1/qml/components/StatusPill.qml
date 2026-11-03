import QtQuick 2.15
import "../theme"

// Subsystem state as [glyph] NAME state-word — colour + shape + text, so colour
// is never the only cue (and a monochrome capture still distinguishes states).
Item {
    id: root
    property string name: ""
    property string status: "unknown"

    implicitHeight: Theme.touch

    Row {
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.gapSm

        Text {
            text: Theme.statusGlyph(root.status)
            color: Theme.statusColor(root.status)
            font.pixelSize: Theme.caption
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            text: root.name
            color: Theme.text
            font.pixelSize: Theme.body
            font.weight: Font.DemiBold
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            text: root.status
            color: Theme.statusColor(root.status)
            font.pixelSize: Theme.body
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
