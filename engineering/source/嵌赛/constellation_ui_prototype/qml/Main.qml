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
    title: qsTr("M29 RML23 星座图离线原型")
    color: theme.background

    Theme { id: theme }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        StatusBar {
            theme: theme
            Layout.fillWidth: true
        }

        // Middle: left ~70% constellation, right ~30% metrics. Both children fill
        // and distribute the extra space in a 7:3 ratio via Layout.preferredWidth.
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: theme.gap
            spacing: theme.gap

            ConstellationScreen {
                theme: theme
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 7
                Layout.minimumWidth: 480
            }
            MetricsPanel {
                theme: theme
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 3
                Layout.minimumWidth: 240
            }
        }

        PlaybackBar {
            theme: theme
            Layout.fillWidth: true
        }
    }
}
