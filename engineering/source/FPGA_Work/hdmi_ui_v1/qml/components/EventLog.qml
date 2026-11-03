import QtQuick 2.15
import "../theme"

PanelFrame {
    title: qsTr("Event log")

    ListView {
        id: list
        anchors.fill: parent
        clip: true
        model: bridge.eventLog
        spacing: 2

        function levelColor(level) {
            if (level === "warning" || level === "error") return Theme.error
            if (level === "info") return Theme.ok
            return Theme.textDim
        }

        onCountChanged: Qt.callLater(list.positionViewAtEnd)

        delegate: Row {
            width: list.width
            height: 28
            spacing: Theme.gapSm

            Text {
                width: 110
                text: modelData.time
                color: Theme.textDim
                font.pixelSize: Theme.small
                verticalAlignment: Text.AlignVCenter
            }
            Text {
                width: 70
                text: modelData.level
                color: list.levelColor(modelData.level)
                font.pixelSize: Theme.small
                font.weight: Font.DemiBold
                verticalAlignment: Text.AlignVCenter
            }
            Text {
                width: list.width - 110 - 70 - 2 * Theme.gapSm
                text: modelData.text
                color: Theme.text
                font.pixelSize: Theme.small
                elide: Text.ElideRight
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
