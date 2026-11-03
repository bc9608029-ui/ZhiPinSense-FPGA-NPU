import QtQuick 2.15
import "../theme"

PanelFrame {
    title: qsTr("Subsystem status")

    Column {
        width: parent.width
        spacing: Theme.gapSm

        StatusBadge {
            name: qsTr("SDR")
            status: bridge.hasFrame ? bridge.frame.sdr_status : "unknown"
        }
        StatusBadge {
            name: qsTr("FPGA")
            status: bridge.hasFrame ? bridge.frame.fpga_status : "unknown"
        }
        StatusBadge {
            name: qsTr("NPU")
            status: bridge.hasFrame ? bridge.frame.npu_status : "unknown"
        }
    }
}
