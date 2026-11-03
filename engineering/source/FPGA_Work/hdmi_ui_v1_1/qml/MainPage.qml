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
            Layout.fillHeight: true
            spacing: Theme.gap

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: Theme.gap

                ClassHeader {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 118
                }
                ProbabilityBars {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                }
            }

            StatusPanel {
                Layout.preferredWidth: 300
                Layout.fillHeight: true
            }
        }

        SourceBar {
            Layout.fillWidth: true
            Layout.preferredHeight: 188
        }
    }
}
