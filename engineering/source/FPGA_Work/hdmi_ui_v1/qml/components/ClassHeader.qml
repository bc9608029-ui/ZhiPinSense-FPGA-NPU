import QtQuick 2.15
import "../theme"

PanelFrame {
    title: qsTr("Classification")

    Column {
        width: parent.width
        spacing: Theme.gapSm

        Text {
            text: bridge.hasFrame ? bridge.frame.class_name : qsTr("—")
            color: Theme.text
            font.pixelSize: Theme.display
            font.weight: Font.Bold
        }

        Row {
            spacing: Theme.gap

            Text {
                text: bridge.hasFrame
                      ? qsTr("confidence %1%").arg(Math.round(bridge.frame.confidence * 100))
                      : qsTr("confidence —")
                color: (bridge.hasFrame && bridge.frame.low_confidence) ? Theme.warning : Theme.text
                font.pixelSize: Theme.h1
                anchors.verticalCenter: parent.verticalCenter
            }

            Rectangle {
                visible: bridge.hasFrame && bridge.frame.low_confidence
                height: 30
                radius: 15
                width: lowConfText.implicitWidth + 24
                color: Theme.warning
                Text {
                    id: lowConfText
                    anchors.centerIn: parent
                    text: qsTr("low confidence")
                    color: Theme.background
                    font.pixelSize: Theme.caption
                    font.weight: Font.DemiBold
                }
            }
        }

        Text {
            visible: bridge.hasFrame
            text: qsTr("SNR %1 dB").arg(bridge.frame.snr_db.toFixed(1))
            color: Theme.textDim
            font.pixelSize: Theme.body
        }
    }
}
