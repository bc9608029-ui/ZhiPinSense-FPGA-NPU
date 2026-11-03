import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "theme"
import "components"

ApplicationWindow {
    id: root
    visible: true
    width: 1920
    height: 1080
    color: Theme.background
    title: qsTr("RF Modulation Recognition")

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.gap
        spacing: Theme.gap

        // ---- Top bar: source + global state + RF parameters ----
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 64
            color: Theme.panel
            radius: Theme.radius
            border.color: Theme.border

            Row {
                anchors.left: parent.left
                anchors.leftMargin: Theme.gapSm
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.gapSm

                Text {
                    text: qsTr("RF AMR")
                    color: Theme.accent
                    font.pixelSize: Theme.h1
                    font.weight: Font.Bold
                    anchors.verticalCenter: parent.verticalCenter
                }

                Rectangle {
                    height: 32
                    radius: 16
                    width: srcText.implicitWidth + 32
                    color: Theme.panelAlt
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        id: srcText
                        anchors.centerIn: parent
                        text: bridge.hasFrame ? bridge.frame.source : qsTr("—")
                        color: Theme.text
                        font.pixelSize: Theme.caption
                        font.weight: Font.DemiBold
                    }
                }

                Rectangle {
                    visible: bridge.stale
                    height: 32
                    radius: 16
                    width: 92
                    color: Theme.warning
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        anchors.centerIn: parent
                        text: qsTr("STALE")
                        color: Theme.background
                        font.pixelSize: Theme.caption
                        font.weight: Font.Bold
                    }
                }

                Rectangle {
                    visible: bridge.hasFrame && bridge.frame.low_confidence
                    height: 32
                    radius: 16
                    width: lowConfText.implicitWidth + 32
                    color: Theme.warning
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        id: lowConfText
                        anchors.centerIn: parent
                        text: qsTr("LOW CONF")
                        color: Theme.background
                        font.pixelSize: Theme.caption
                        font.weight: Font.Bold
                    }
                }
            }

            Text {
                anchors.right: parent.right
                anchors.rightMargin: Theme.gapSm
                anchors.verticalCenter: parent.verticalCenter
                text: bridge.hasFrame
                      ? qsTr("RF %1 GHz · %2 ksps · %3 fps")
                            .arg((bridge.frame.center_frequency_hz / 1e9).toFixed(3))
                            .arg((bridge.frame.sample_rate_hz / 1e3).toFixed(0))
                            .arg(bridge.frame.fps.toFixed(1))
                      : qsTr("RF — · — · —")
                color: Theme.textDim
                font.pixelSize: Theme.body
            }
        }

        // ---- Primary + status columns ----
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.gap

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1150
                spacing: Theme.gap

                ClassHeader {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 210
                }
                ProbabilityBars {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 340
                }
                SpectrumView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                }
            }

            ColumnLayout {
                Layout.preferredWidth: 690
                Layout.fillHeight: true
                spacing: Theme.gap

                StatusPanel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 200
                }
                LatencyPanel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 320
                }
                CountersPanel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                }
            }
        }

        // ---- Event log + source selector ----
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 250
            spacing: Theme.gap

            EventLog {
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
            SourceBar {
                Layout.preferredWidth: 620
                Layout.fillHeight: true
            }
        }
    }
}
