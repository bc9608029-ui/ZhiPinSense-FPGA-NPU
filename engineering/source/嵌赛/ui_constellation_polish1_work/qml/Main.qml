import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// Main.qml — application window: StatusBar (top), constellation + metrics
// (middle), PlaybackBar (bottom). The Controller is injected from C++ as the
// "controller" context property; all data comes from it (real IQ files only).
ApplicationWindow {
    id: root
    visible: true
    width: 1280
    height: 720
    minimumWidth: 420
    minimumHeight: 320
    title: qsTr("M29 RML24 信号识别与星座分析")
    color: theme.background
    property bool compactLayout: width < 900

    Theme { id: theme }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        StatusBar {
            theme: theme
            Layout.fillWidth: true
        }

        Flickable {
            id: workspace
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: width
            contentHeight: Math.max(height, workspaceGrid.implicitHeight + theme.gap * 2)
            boundsBehavior: Flickable.StopAtBounds

            GridLayout {
                id: workspaceGrid
                x: theme.gap
                y: theme.gap
                width: workspace.width - theme.gap * 2
                height: root.compactLayout ? implicitHeight : workspace.height - theme.gap * 2
                columns: root.compactLayout ? 1 : 2
                columnSpacing: theme.gap
                rowSpacing: theme.gap

                ConstellationScreen {
                    theme: theme
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 7
                    Layout.minimumWidth: 320
                    Layout.minimumHeight: root.compactLayout ? 360 : 300
                }
                MetricsPanel {
                    theme: theme
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 3
                    Layout.minimumWidth: root.compactLayout ? 320 : 260
                    Layout.minimumHeight: root.compactLayout ? 420 : 300
                }
            }

            ScrollBar.vertical: ScrollBar { visible: root.compactLayout }
        }

        PlaybackBar {
            theme: theme
            Layout.fillWidth: true
        }
    }
}
