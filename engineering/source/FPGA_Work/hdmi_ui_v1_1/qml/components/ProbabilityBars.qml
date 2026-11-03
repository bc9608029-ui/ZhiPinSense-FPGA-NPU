import QtQuick 2.15
import "../theme"

PanelFrame {
    title: qsTr("Class probabilities")

    // Two columns; scrolls vertically when a frame declares more classes than
    // fit (up to the contract maximum of 16).
    Flickable {
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: grid.height

    Grid {
        id: grid
        width: parent.width
        columns: 2
        columnSpacing: Theme.gapSm
        rowSpacing: 4

        Repeater {
            model: bridge.frame.class_names

            Item {
                width: (grid.width - Theme.gapSm) / 2
                height: 30

                function fraction(i) {
                    if (!bridge.hasFrame) return 0
                    var s = bridge.frame.scores[i]
                    return s === undefined ? 0 : s
                }

                function isCurrent(i) {
                    return bridge.hasFrame && bridge.frame.predicted_index === i
                }

                Text {
                    id: label
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: 84
                    text: modelData
                    color: isCurrent(index) ? Theme.text : Theme.textDim
                    font.pixelSize: Theme.caption
                    font.weight: isCurrent(index) ? Font.DemiBold : Font.Normal
                    elide: Text.ElideRight
                }

                Rectangle {
                    anchors.left: label.right
                    anchors.leftMargin: Theme.gapSm
                    anchors.right: pct.left
                    anchors.rightMargin: Theme.gapSm
                    anchors.verticalCenter: parent.verticalCenter
                    height: 14
                    radius: 7
                    color: Theme.panelAlt

                    Rectangle {
                        width: parent.width * fraction(index)
                        height: parent.height
                        radius: parent.radius
                        color: isCurrent(index) ? Theme.accent : Theme.ok
                    }
                }

                Text {
                    id: pct
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    width: 48
                    text: Math.round(fraction(index) * 100) + "%"
                    color: Theme.textDim
                    font.pixelSize: Theme.small
                    horizontalAlignment: Text.AlignRight
                }
            }
        }
    }
    }
}
