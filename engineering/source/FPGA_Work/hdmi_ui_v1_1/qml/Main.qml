import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "theme"
import "components"

ApplicationWindow {
    id: root
    visible: true
    width: 1024
    height: 600
    color: Theme.background
    title: qsTr("RF Modulation Recognition")

    property int page: 0

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.gap
        spacing: Theme.gap

        TopBar {
            Layout.fillWidth: true
            currentPage: root.page
            onPageSelected: root.page = index
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.page

            MainPage {}
            DiagnosticsPage {}
        }
    }
}
