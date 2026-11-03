import QtQuick 2.15
import "../theme"

PanelFrame {
    title: qsTr("Diagnostics")

    Column {
        id: content
        width: parent.width
        spacing: Theme.gapSm

        function seq(key) {
            var v = bridge.sequence[key]
            return v === undefined ? 0 : v
        }
        function ctr(key) {
            if (!bridge.hasFrame) return 0
            var v = bridge.frame.counters[key]
            return v === undefined ? 0 : v
        }

        StatusPill {
            name: qsTr("Flow")
            status: !bridge.hasFrame ? "unknown" : (bridge.stale ? "stale" : "ok")
        }

        Text {
            text: qsTr("Sequence monitor (consumer-detected)")
            color: Theme.textDim
            font.pixelSize: Theme.caption
        }

        Grid {
            id: seqGrid
            width: parent.width
            columns: 2
            columnSpacing: Theme.gap
            rowSpacing: 2

            Repeater {
                model: [
                    { label: qsTr("frame count"),  key: "seen",      warn: false },
                    { label: qsTr("dropped"),      key: "dropped",   warn: true },
                    { label: qsTr("out-of-order"), key: "reorder",   warn: true },
                    { label: qsTr("duplicate"),    key: "duplicate", warn: true },
                    { label: qsTr("gaps"),         key: "gap",       warn: true }
                ]

                Row {
                    width: (seqGrid.width - Theme.gap) / 2
                    height: 26
                    spacing: Theme.gapSm

                    Text {
                        text: modelData.label
                        color: Theme.textDim
                        font.pixelSize: Theme.body
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: content.seq(modelData.key)
                        color: (modelData.warn && content.seq(modelData.key) > 0) ? Theme.error : Theme.text
                        font.pixelSize: Theme.body
                        font.weight: Font.DemiBold
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }

        Text {
            text: qsTr("Producer counters (reported)")
            color: Theme.textDim
            font.pixelSize: Theme.caption
        }

        Grid {
            id: ctrGrid
            width: parent.width
            columns: 2
            columnSpacing: Theme.gap
            rowSpacing: 2

            Repeater {
                model: [
                    { label: qsTr("dropped"),  key: "dropped" },
                    { label: qsTr("overflow"), key: "overflow" },
                    { label: qsTr("duplicate"), key: "duplicate" },
                    { label: qsTr("reorder"),  key: "reorder" },
                    { label: qsTr("timeout"),  key: "timeout" },
                    { label: qsTr("error"),    key: "error" }
                ]

                Row {
                    width: (ctrGrid.width - Theme.gap) / 2
                    height: 26
                    spacing: Theme.gapSm

                    Text {
                        text: modelData.label
                        color: Theme.textDim
                        font.pixelSize: Theme.body
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: content.ctr(modelData.key)
                        color: content.ctr(modelData.key) > 0 ? Theme.error : Theme.text
                        font.pixelSize: Theme.body
                        font.weight: Font.DemiBold
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }
    }
}
