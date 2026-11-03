import QtQuick 2.15
import QtQuick.Layouts 1.15

// MetricsPanel.qml — right pane (~30%): predicted class, confidence, baseline
// class, agreement, CFO/SRO/gain, sample rate, SHA validation, timing validity,
// and frame/point bookkeeping. All values come from the C++ Controller (real
// data only — nothing fabricated).
Rectangle {
    id: root
    property QtObject theme: null

    color: theme.panelBackground
    border.color: theme.border
    border.width: 1
    radius: theme.radius

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.gap * 2
        spacing: theme.gap

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: qsTr("识别结果")
                color: theme.textPrimary
                font.pixelSize: theme.fontSizeLarge
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                Layout.preferredWidth: engineLabel.implicitWidth + 18
                Layout.preferredHeight: 24
                radius: 12
                color: theme.panelMuted
                border.color: theme.border
                Text {
                    id: engineLabel
                    anchors.centerIn: parent
                    text: qsTr("BF16 · 24 类")
                    color: theme.accentBlue
                    font.pixelSize: theme.fontSizeSmall
                    font.bold: true
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 104
            radius: theme.radius
            color: theme.panelElevated
            border.color: theme.borderStrong

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: theme.gap
                spacing: 2

                Text {
                    text: qsTr("当前识别")
                    color: theme.textSecondary
                    font.pixelSize: theme.fontSizeSmall
                }
                Text {
                    Layout.fillWidth: true
                    text: controller.predictedClass === "" ? qsTr("等待数据") : controller.predictedClass
                    color: theme.accent
                    font.pixelSize: theme.fontSizeHero
                    font.bold: true
                    elide: Text.ElideRight
                }
                Text {
                    text: qsTr("置信度 %1").arg(controller.confidenceText)
                    color: controller.confidenceValid ? theme.textPrimary : theme.textFaint
                    font.pixelSize: theme.fontSizeNormal
                }
            }
        }

        Text {
            text: qsTr("链路指标")
            color: theme.textPrimary
            font.pixelSize: theme.fontSizeNormal
            font.bold: true
        }
        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: theme.border }
        MetricRow {
            theme: root.theme; Layout.fillWidth: true
            label: qsTr("基线类别")
            value: controller.baselineClass
        }
        MetricRow {
            theme: root.theme; Layout.fillWidth: true
            label: qsTr("预测一致性")
            value: controller.agreement ? qsTr("一致") : qsTr("不一致")
            valueColor: controller.agreement ? theme.accent : theme.danger
        }
        MetricRow {
            theme: root.theme; Layout.fillWidth: true
            label: qsTr("CFO")
            value: controller.cfoText
            valueColor: controller.cfoValid ? theme.textPrimary : theme.textFaint
        }
        MetricRow {
            theme: root.theme; Layout.fillWidth: true
            label: qsTr("SRO")
            value: controller.sroText
            valueColor: controller.sroValid ? theme.textPrimary : theme.textFaint
        }
        MetricRow {
            theme: root.theme; Layout.fillWidth: true
            label: qsTr("增益幅度")
            value: controller.gainText
            valueColor: controller.gainValid ? theme.textPrimary : theme.textFaint
        }
        MetricRow {
            theme: root.theme; Layout.fillWidth: true
            label: qsTr("D2 恢复标量")
            value: controller.d2RecScaleText
            visible: controller.d2RecScaleText !== ""
        }
        MetricRow {
            theme: root.theme; Layout.fillWidth: true
            label: qsTr("采样率")
            value: controller.sampleRateText
        }
        MetricRow {
            theme: root.theme; Layout.fillWidth: true
            label: qsTr("SHA 校验")
            value: controller.shaValid ? qsTr("通过") : qsTr("失败")
            valueColor: controller.shaValid ? theme.accent : theme.danger
        }
        MetricRow {
            theme: root.theme; Layout.fillWidth: true
            label: qsTr("符号定时")
            value: controller.timingValid ? qsTr("有效") : qsTr("无效")
            valueColor: controller.timingValid ? theme.textPrimary : theme.textFaint
        }

        Text {
            text: qsTr("数据完整性")
            color: theme.textPrimary
            font.pixelSize: theme.fontSizeNormal
            font.bold: true
        }
        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: theme.border }

        MetricRow {
            theme: root.theme; Layout.fillWidth: true
            label: qsTr("帧")
            value: controller.frameIndex + " / " + controller.frameCount
        }
        MetricRow {
            theme: root.theme; Layout.fillWidth: true
            label: qsTr("总点数")
            value: controller.totalPoints
        }
        MetricRow {
            theme: root.theme; Layout.fillWidth: true
            label: qsTr("显示点数")
            value: controller.pointCount
        }
        MetricRow {
            theme: root.theme; Layout.fillWidth: true
            label: qsTr("SHA 摘要")
            value: controller.sourceSha
            valueColor: theme.textFaint
        }

        Item { Layout.fillHeight: true }
    }
}
