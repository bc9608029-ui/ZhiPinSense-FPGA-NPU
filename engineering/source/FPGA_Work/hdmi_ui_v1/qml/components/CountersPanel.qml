import QtQuick 2.15
import "../theme"

PanelFrame {
    title: qsTr("Anomaly counters")

    Column {
        id: content
        width: parent.width
        spacing: Theme.gapSm

        function value(key) {
            if (!bridge.hasFrame) return 0
            var v = bridge.frame.counters[key]
            return v === undefined ? 0 : v
        }

        Grid {
            width: parent.width
            columns: 2
            columnSpacing: Theme.gap
            rowSpacing: Theme.gapSm

            Repeater {
                model: [
                    { key: "dropped",   label: qsTr("dropped") },
                    { key: "overflow",  label: qsTr("overflow") },
                    { key: "duplicate", label: qsTr("duplicate") },
                    { key: "reorder",   label: qsTr("reorder") },
                    { key: "timeout",   label: qsTr("timeout") },
                    { key: "error",     label: qsTr("error") }
                ]

                Row {
                    width: content.width / 2 - Theme.gap / 2
                    height: 40
                    spacing: Theme.gapSm

                    Text {
                        text: modelData.label
                        color: Theme.textDim
                        font.pixelSize: Theme.body
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Text {
                        text: content.value(modelData.key)
                        color: content.value(modelData.key) > 0 ? Theme.error : Theme.text
                        font.pixelSize: Theme.body
                        font.weight: Font.DemiBold
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }
    }
}
