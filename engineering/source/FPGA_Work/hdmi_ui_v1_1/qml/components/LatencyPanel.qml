import QtQuick 2.15
import "../theme"

PanelFrame {
    title: qsTr("Latency")

    Column {
        id: content
        width: parent.width
        spacing: Theme.gapSm

        function value(key) {
            if (!bridge.hasFrame) return 0
            var v = bridge.frame.latency_us[key]
            return v === undefined ? 0 : v
        }

        Repeater {
            model: [
                { key: "sdr_capture",    label: qsTr("SDR capture") },
                { key: "resample_frame", label: qsTr("Resample") },
                { key: "plddr_transfer", label: qsTr("PL-DDR transfer") },
                { key: "fpga_process",   label: qsTr("FPGA process") },
                { key: "npu_infer",      label: qsTr("NPU infer") },
                { key: "end_to_end",     label: qsTr("End-to-end") }
            ]

            Item {
                width: content.width
                height: 28

                Text {
                    id: label
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: 140
                    text: modelData.label
                    color: Theme.textDim
                    font.pixelSize: Theme.caption
                    elide: Text.ElideRight
                }

                Rectangle {
                    anchors.left: label.right
                    anchors.leftMargin: Theme.gapSm
                    anchors.right: value.left
                    anchors.rightMargin: Theme.gapSm
                    anchors.verticalCenter: parent.verticalCenter
                    height: 14
                    radius: 7
                    color: Theme.panelAlt

                    Rectangle {
                        // Full scale = 1000 µs.
                        width: Math.min(parent.width, parent.width * content.value(modelData.key) / 1000)
                        height: parent.height
                        radius: parent.radius
                        color: modelData.key === "end_to_end" ? Theme.accent : Theme.ok
                    }
                }

                Text {
                    id: value
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    width: 90
                    text: content.value(modelData.key).toFixed(1) + qsTr(" µs")
                    color: Theme.text
                    font.pixelSize: Theme.small
                    horizontalAlignment: Text.AlignRight
                }
            }
        }
    }
}
