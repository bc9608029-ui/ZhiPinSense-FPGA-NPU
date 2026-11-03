import QtQuick 2.15
import "../theme"

// Subsystem state as [shape] NAME state-word — colour is never the only cue.
Item {
    id: root
    property string name: ""
    property string status: "unknown"

    height: Theme.touch

    Row {
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.gapSm

        Rectangle {
            width: 16
            height: 16
            radius: 8
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.statusColor(root.status)
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
