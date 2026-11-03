import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Dialogs 1.3

// PlaybackBar.qml — bottom control bar: open data, prev/next, coordinate mode
// (AUTO / FIXED ±1 / FIXED ±2 / CUSTOM), point-count limit, pause/resume,
// screenshot and export. All actions route to the C++ Controller; the bar does
// no data parsing of its own.
Rectangle {
    id: root
    property QtObject theme: null
    property string feedbackText: ""

    implicitHeight: Math.max(52, theme.fontSizeNormal + 28)
    color: theme.panelBackground

    Rectangle {
        anchors.top: parent.top
        width: parent.width
        height: 1
        color: theme.border
    }

    function ts() {
        return Qt.formatDateTime(new Date(), "yyyyMMdd_hhmmss_zzz")
    }
    function showFeedback(msg) {
        feedbackText = msg
        feedbackTimer.restart()
    }

    Timer {
        id: feedbackTimer
        interval: 4000
        onTriggered: feedbackText = ""
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.gap
        anchors.rightMargin: theme.gap
        spacing: theme.gap

        Button { focusPolicy: Qt.StrongFocus; text: qsTr("打开数据…"); onClicked: openFileDialog.open() }
        Button { focusPolicy: Qt.StrongFocus; text: qsTr("打开目录…"); onClicked: openDirDialog.open() }
        Button {
            focusPolicy: Qt.StrongFocus
            text: qsTr("上一帧")
            onClicked: controller.previousFrame()
            enabled: controller.frameCount > 1
        }
        Button {
            focusPolicy: Qt.StrongFocus
            text: qsTr("下一帧")
            onClicked: controller.nextFrame()
            enabled: controller.frameCount > 1
        }
        Button {
            focusPolicy: Qt.StrongFocus
            text: controller.paused ? qsTr("继续") : qsTr("暂停")
            onClicked: controller.togglePause()
            enabled: controller.frameCount > 1 || controller.loop
        }

        Text {
            text: qsTr("坐标：")
            color: theme.textSecondary
            font.pixelSize: theme.fontSizeNormal
            Layout.alignment: Qt.AlignVCenter
        }
        ComboBox {
            id: coordBox
            model: [ qsTr("自动"), qsTr("固定 ±1"), qsTr("固定 ±2"), qsTr("自定义") ]
            currentIndex: 0
            Layout.alignment: Qt.AlignVCenter
            Accessible.name: qsTr("坐标模式")
            onActivated: controller.setCoordinateMode(["AUTO", "FIXED_1", "FIXED_2", "CUSTOM"][index])
        }
        SpinBox {
            id: rangeSpin
            from: 10          // 0.10 (integer backend x100; Qt 5.15 SpinBox is int-only)
            to: 10000         // 100.00
            stepSize: 10      // 0.10
            editable: true
            value: Math.round(controller.customRange * 100)
            enabled: coordBox.currentIndex === 3
            Layout.alignment: Qt.AlignVCenter
            Accessible.name: qsTr("自定义坐标范围")
            textFromValue: function(v, locale) { return Number(v / 100).toFixed(2) }
            valueFromText: function(text, locale) {
                return Math.round(Number.fromLocaleString(locale, text) * 100)
            }
            onValueModified: controller.setCustomRange(value / 100)
        }

        Text {
            text: qsTr("点数上限：")
            color: theme.textSecondary
            font.pixelSize: theme.fontSizeNormal
            Layout.alignment: Qt.AlignVCenter
        }
        ComboBox {
            model: [ 1024, 2048, 4096 ]
            currentIndex: 2
            Layout.alignment: Qt.AlignVCenter
            Accessible.name: qsTr("点数上限")
            onActivated: controller.setPointLimit(model[index])
        }

        Item { Layout.fillWidth: true }

        Button { focusPolicy: Qt.StrongFocus; text: qsTr("截图"); onClicked: doScreenshot() }
        Button { focusPolicy: Qt.StrongFocus; text: qsTr("导出…"); onClicked: exportMenu.popup() }

        Text {
            text: feedbackText
            color: theme.textSecondary
            font.pixelSize: theme.fontSizeSmall
            Layout.maximumWidth: 220
            elide: Text.ElideLeft
            visible: feedbackText !== ""
            Layout.alignment: Qt.AlignVCenter
        }
    }

    function doScreenshot() {
        var r = controller.screenshot("constellation_screenshot_" + ts() + ".png")
        showFeedback(r === "" ? qsTr("已保存截图") : qsTr("截图失败：") + r)
    }

    Menu {
        id: exportMenu
        MenuItem {
            text: qsTr("导出帧 JSON")
            onTriggered: {
                var r = controller.exportFrameJson("constellation_frame_" + ts() + ".json")
                showFeedback(r === "" ? qsTr("已导出帧 JSON") : qsTr("导出失败：") + r)
            }
        }
        MenuItem {
            text: qsTr("导出当前点 CSV")
            onTriggered: {
                var r = controller.exportCsv("constellation_points_" + ts() + ".csv")
                showFeedback(r === "" ? qsTr("已导出 CSV") : qsTr("导出失败：") + r)
            }
        }
        MenuItem {
            text: qsTr("导出诊断")
            onTriggered: {
                var r = controller.exportDiagnostic("constellation_diagnostic_" + ts() + ".txt")
                showFeedback(r === "" ? qsTr("已导出诊断") : qsTr("导出失败：") + r)
            }
        }
    }

    FileDialog {
        id: openFileDialog
        title: qsTr("打开 sidecar JSON")
        selectFolder: false
        nameFilters: [ qsTr("JSON 元数据 (*.json)") ]
        onAccepted: controller.openSidecar(fileUrl)
    }
    FileDialog {
        id: openDirDialog
        title: qsTr("打开数据目录")
        selectFolder: true
        onAccepted: controller.openDirectory(folder)
    }
}
