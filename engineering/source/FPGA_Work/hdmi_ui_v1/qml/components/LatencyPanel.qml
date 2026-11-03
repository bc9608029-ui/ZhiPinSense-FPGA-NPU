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

            Row {
                width: content.width
                height: 30
                spacing: Theme.gapSm

                Text {
                    width: 180
                    text: modelData.label
                    color: Theme.textDim
                    font.pixelSize: Theme.caption
                    anchors.verticalCenter: parent.verticalCenter
                }

                Rectangle {
                    width: 170
                    height: 14
                    radius: 7
                    color: Theme.panelAlt
                    anchors.verticalCenter: parent.verticalCenter

                    Rectangle {
                        // Full scale = 1000 µs.
                        width: Math.min(parent.width, parent.width * content.value(modelData.key) / 1000)
                        height: parent.height
                        radius: parent.radius
                        color: Theme.accent
                    }
                }

                Text {
                    width: 150
                    text: content.value(modelData.key).toFixed(1) + qsTr(" µs")
                    color: Theme.text
                    font.pixelSize: Theme.small
                    horizontalAlignment: Text.AlignRight
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }
    }
}
