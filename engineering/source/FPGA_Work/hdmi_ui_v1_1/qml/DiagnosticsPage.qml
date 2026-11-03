import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../theme"
import "../components"

Item {
    ColumnLayout {
        anchors.fill: parent
        spacing: Theme.gap

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 250
            spacing: Theme.gap

            LatencyPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
            CountersPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
        }

        EventLog {
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
