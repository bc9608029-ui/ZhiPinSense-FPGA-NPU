import QtQuick 2.15
import "../theme"

PanelFrame {
    title: qsTr("Status")

    Column {
        width: parent.width
        spacing: Theme.gapSm

        function overall() {
            if (!bridge.hasFrame) return "unknown"
            if (bridge.stale) return "stale"
            var a = [bridge.frame.sdr_status, bridge.frame.fpga_status, bridge.frame.npu_status]
            if (a.indexOf("error") >= 0) return "error"
            if (a.indexOf("warning") >= 0) return "warning"
            return "ok"
        }

        function overallLabel() {
            switch (overall()) {
            case "ok":      return qsTr("normal")
            case "stale":   return qsTr("stale")
            case "error":   return qsTr("error")
            case "warning": return qsTr("warning")
            default:        return qsTr("waiting")
            }
        }

        Row {
            spacing: Theme.gapSm
            Text {
                text: Theme.statusGlyph(overall())
                color: Theme.statusColor(overall())
                font.pixelSize: Theme.h1
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: qsTr("Running:")
                color: Theme.textDim
                font.pixelSize: Theme.h1
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: overallLabel()
                color: Theme.statusColor(overall())
                font.pixelSize: Theme.h1
                font.weight: Font.Bold
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        Text {
            text: bridge.hasFrame
                  ? qsTr("End-to-end latency %1 µs").arg(bridge.frame.latency_us.end_to_end.toFixed(1))
                  : qsTr("End-to-end latency —")
            color: Theme.text
            font.pixelSize: Theme.body
        }

        StatusPill {
            name: qsTr("SDR")
            status: bridge.hasFrame ? bridge.frame.sdr_status : "unknown"
        }
        StatusPill {
            name: qsTr("FPGA")
            status: bridge.hasFrame ? bridge.frame.fpga_status : "unknown"
        }
        StatusPill {
            name: qsTr("NPU")
            status: bridge.hasFrame ? bridge.frame.npu_status : "unknown"
        }
    }
}
