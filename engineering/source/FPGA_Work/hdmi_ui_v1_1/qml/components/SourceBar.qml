import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../theme"

PanelFrame {
    title: qsTr("Data source")

    function pretty(s) {
        var words = s.split("_")
        for (var i = 0; i < words.length; i++)
            words[i] = words[i].charAt(0).toUpperCase() + words[i].slice(1)
        return words.join(" ")
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: Theme.gapSm

        RowLayout {
            spacing: Theme.gapSm
            Text {
                text: qsTr("Mock:")
                color: Theme.textDim
                font.pixelSize: Theme.caption
            }
            Flickable {
                Layout.fillWidth: true
                Layout.preferredHeight: Theme.touch
                clip: true
                contentWidth: scenarioRow.width
                contentHeight: Theme.touch
                interactive: contentWidth > width

                Row {
                    id: scenarioRow
                    height: Theme.touch
                    spacing: Theme.gapSm

                    Repeater {
                        model: sourceController.mockScenarios()
                        ActionButton {
                            text: pretty(modelData)
                            onClicked: sourceController.startMock(modelData)
                        }
                    }
                }
            }
        }

        RowLayout {
            spacing: Theme.gapSm
            Text {
                text: qsTr("File:")
                color: Theme.textDim
                font.pixelSize: Theme.caption
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Theme.touch
                radius: Theme.radius
                color: Theme.panelAlt
                border.color: Theme.border
                TextInput {
                    id: filePath
                    anchors.fill: parent
                    anchors.margins: Theme.gapSm
                    color: Theme.text
                    font.pixelSize: Theme.body
                    verticalAlignment: TextInput.AlignVCenter
                    clip: true
                    text: "mock_data/normal.jsonl"
                }
            }
            ActionButton {
                text: qsTr("Load")
                onClicked: sourceController.startFile(filePath.text)
            }
        }

        RowLayout {
            spacing: Theme.gapSm
            Text {
                text: qsTr("Socket:")
                color: Theme.textDim
                font.pixelSize: Theme.caption
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Theme.touch
                radius: Theme.radius
                color: Theme.panelAlt
                border.color: Theme.border
                TextInput {
                    id: socketPath
                    anchors.fill: parent
                    anchors.margins: Theme.gapSm
                    color: Theme.text
                    font.pixelSize: Theme.body
                    verticalAlignment: TextInput.AlignVCenter
                    clip: true
                    text: "/tmp/hdmi_ui.sock"
                }
            }
            ActionButton {
                text: qsTr("Connect")
                onClicked: sourceController.startUnixSocket(socketPath.text)
            }
            ActionButton {
                text: qsTr("Stop")
                onClicked: sourceController.stop()
            }
        }
    }
}
