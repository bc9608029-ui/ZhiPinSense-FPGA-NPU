import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// StatusBar.qml — top status bar. Always shows the OFFLINE badge and the offline
// file source; NEVER shows "LIVE". Shows stage, class, file/frame id, validation
// status (green, only when no error), and a persistent error slot (red + text +
// dismiss + full-text tooltip). The error slot is separate from the normal
// validation status, so a later normal status never overwrites an error.
Rectangle {
    id: root
    property QtObject theme: null

    implicitHeight: Math.max(40, theme.fontSizeNormal + 24)
    color: theme.panelBackground

    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: theme.border
    }

    function stageLabel(s) {
        switch (s) {
            case "RAW_RX":            return qsTr("原始接收")
            case "RECOVERED_PAYLOAD": return qsTr("恢复载荷")
            case "MODEL_INPUT":       return qsTr("模型输入")
            case "SYMBOL_SAMPLED":    return qsTr("符号采样")
            default:                  return s
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.gap * 2
        anchors.rightMargin: theme.gap * 2
        spacing: theme.gap * 2

        Rectangle {
            Layout.alignment: Qt.AlignVCenter
            Layout.preferredHeight: 22
            Layout.preferredWidth: badgeText.implicitWidth + 20
            radius: 11
            color: "#332A10"
            border.color: theme.offlineBadge
            Text {
                id: badgeText
                anchors.centerIn: parent
                text: qsTr("离线 OFFLINE")
                color: theme.offlineBadge
                font.pixelSize: theme.fontSizeSmall
                font.bold: true
            }
        }

        Text {
            Layout.alignment: Qt.AlignVCenter
            text: qsTr("数据源：") + controller.dataSource
            color: theme.textPrimary
            font.pixelSize: theme.fontSizeNormal
        }
        Text {
            Layout.alignment: Qt.AlignVCenter
            text: qsTr("阶段：") + stageLabel(controller.stage)
            color: theme.textPrimary
            font.pixelSize: theme.fontSizeNormal
        }
        Text {
            Layout.alignment: Qt.AlignVCenter
            text: qsTr("类别：") + controller.predictedClass
            color: theme.textPrimary
            font.pixelSize: theme.fontSizeNormal
        }
        Text {
            Layout.alignment: Qt.AlignVCenter
            text: controller.fileName + qsTr("  帧#") + controller.frameId
            color: theme.textSecondary
            font.pixelSize: theme.fontSizeNormal
        }
        // Normal validation status (green) — shown only while there is no error.
        Text {
            Layout.alignment: Qt.AlignVCenter
            visible: controller.errorText === "" && controller.validationStatus !== ""
            text: controller.validationStatus
            color: theme.accent
            font.pixelSize: theme.fontSizeNormal
        }

        Item { Layout.fillWidth: true }

        // Persistent error (red + text + dismiss + full-text tooltip).
        Text {
            id: errorLabel
            Layout.alignment: Qt.AlignVCenter
            Layout.maximumWidth: 320
            visible: controller.errorText !== ""
            text: qsTr("错误：") + controller.errorText
            color: theme.danger
            font.pixelSize: theme.fontSizeNormal
            elide: Text.ElideMiddle
            ToolTip.visible: errorMouse.containsMouse
            ToolTip.text: controller.errorText
            ToolTip.delay: 300
            MouseArea {
                id: errorMouse
                anchors.fill: parent
                hoverEnabled: true
            }
        }
        Button {
            focusPolicy: Qt.StrongFocus
            Layout.alignment: Qt.AlignVCenter
            visible: controller.errorText !== ""
            text: qsTr("×")
            Accessible.name: qsTr("清除错误")
            onClicked: controller.clearError()
            ToolTip.visible: hovered
            ToolTip.text: qsTr("清除错误")
        }

        Text {
            Layout.alignment: Qt.AlignVCenter
            Layout.maximumWidth: 280
            text: controller.warning
            color: theme.warning
            font.pixelSize: theme.fontSizeSmall
            elide: Text.ElideLeft
            visible: controller.warning !== ""
        }
    }
}
