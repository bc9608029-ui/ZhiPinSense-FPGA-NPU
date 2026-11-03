import QtQuick 2.15
import "../theme"

PanelFrame {
    title: qsTr("Probabilities")

    Column {
        id: content
        width: parent.width
        spacing: Theme.gapSm

        function fraction(i) {
            if (!bridge.hasFrame) return 0
            var p = bridge.frame.probabilities[i]
            return p === undefined ? 0 : p
        }

        function isCurrent(i) {
            return bridge.hasFrame && bridge.frame.class_id === i
        }

        Repeater {
            model: classNames

            Row {
                width: content.width
                height: 30
                spacing: Theme.gapSm

                Text {
                    width: 88
                    text: modelData
                    color: Theme.textDim
                    font.pixelSize: Theme.caption
                    font.weight: content.isCurrent(index) ? Font.DemiBold : Font.Normal
                    anchors.verticalCenter: parent.verticalCenter
                }

                Rectangle {
                    width: content.width - 88 - Theme.gapSm - 64
                    height: 14
                    radius: 7
                    color: Theme.panelAlt
                    anchors.verticalCenter: parent.verticalCenter

                    Rectangle {
                        width: parent.width * content.fraction(index)
                        height: parent.height
                        radius: parent.radius
                        color: content.isCurrent(index) ? Theme.accent : Theme.ok
                    }
                }

                Text {
                    width: 64
                    text: Math.round(content.fraction(index) * 100) + "%"
                    color: Theme.textDim
                    font.pixelSize: Theme.small
                    horizontalAlignment: Text.AlignRight
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }
    }
}
