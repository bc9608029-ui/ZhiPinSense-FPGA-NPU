import QtQuick 2.15
import QtQuick.Layouts 1.15

// ConstellationScreen.qml — left pane (~70%): title + legend, the plot area,
// and a footer with point count / range / coordinate mode / out-of-range count.
Rectangle {
    id: root
    property QtObject theme: null

    color: theme.panelBackground
    border.color: theme.border
    border.width: 1
    radius: theme.radius

    function modeLabel(m) {
        switch (m) {
            case "AUTO":     return qsTr("自动")
            case "FIXED_1":  return qsTr("固定 ±1")
            case "FIXED_2":  return qsTr("固定 ±2")
            case "CUSTOM":   return qsTr("自定义")
            default:         return m
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.gap
        spacing: theme.gap

        RowLayout {
            Layout.fillWidth: true

            Text {
                text: qsTr("实时星座分析")
                color: theme.textPrimary
                font.pixelSize: theme.fontSizeLarge
                font.bold: true
                Layout.alignment: Qt.AlignVCenter
            }
            Text {
                text: qsTr("同轴 I/Q · 原点居中 · 等比例")
                color: theme.textFaint
                font.pixelSize: theme.fontSizeSmall
                Layout.alignment: Qt.AlignVCenter
            }
            Item { Layout.fillWidth: true }
            LegendDot { theme: root.theme; dotColor: theme.rawRx;            label: qsTr("原始接收"); Layout.alignment: Qt.AlignVCenter }
            LegendDot { theme: root.theme; dotColor: theme.recoveredPayload; label: qsTr("恢复载荷"); Layout.alignment: Qt.AlignVCenter }
            LegendDot { theme: root.theme; dotColor: theme.modelInput;       label: qsTr("模型输入"); Layout.alignment: Qt.AlignVCenter }
            LegendDot { theme: root.theme; dotColor: theme.symbolSampled;    label: qsTr("符号采样"); Layout.alignment: Qt.AlignVCenter }
            LegendDot { theme: root.theme; dotColor: theme.outlier;          label: qsTr("越界");   Layout.alignment: Qt.AlignVCenter }
        }

        Text {
            Layout.fillWidth: true
            text: qsTr("RAW_RX 暂无真实夹具（本原型不含伪造的原始接收数据，未用 D2 TX/冻结载荷冒充）")
            color: theme.textFaint
            font.pixelSize: theme.fontSizeSmall
            wrapMode: Text.WordWrap
        }

        ConstellationPlot {
            theme: root.theme
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: qsTr("显示点数：%1 / %2").arg(controller.pointCount).arg(controller.totalPoints)
                color: theme.textSecondary
                font.pixelSize: theme.fontSizeSmall
                Layout.alignment: Qt.AlignVCenter
            }
            Text {
                text: qsTr("范围：±%1").arg(controller.range.toFixed(3))
                color: theme.textSecondary
                font.pixelSize: theme.fontSizeSmall
                Layout.alignment: Qt.AlignVCenter
            }
            Text {
                text: qsTr("模式：%1").arg(modeLabel(controller.coordinateMode))
                color: theme.textSecondary
                font.pixelSize: theme.fontSizeSmall
                Layout.alignment: Qt.AlignVCenter
            }
            Text {
                text: qsTr("越界：%1").arg(controller.outOfRangeCount)
                color: controller.outOfRangeCount > 0 ? theme.outlier : theme.textSecondary
                font.pixelSize: theme.fontSizeSmall
                Layout.alignment: Qt.AlignVCenter
            }
            Item { Layout.fillWidth: true }
        }
    }
}
