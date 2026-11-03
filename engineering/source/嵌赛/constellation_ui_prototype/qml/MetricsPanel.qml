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

        Text {
            text: qsTr("指标")
            color: theme.textPrimary
            font.pixelSize: theme.fontSizeLarge
            font.bold: true
        }
        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: theme.border }

        MetricRow {
            theme: root.theme; Layout.fillWidth: true
            label: qsTr("预测类别")
            value: controller.predictedClass
            valueColor: theme.accent
            valueBold: true
        }
        MetricRow {
            theme: root.theme; Layout.fillWidth: true
            label: qsTr("置信度")
            value: controller.confidenceText
            valueColor: controller.confidenceValid ? theme.textPrimary : theme.textFaint
        }
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
