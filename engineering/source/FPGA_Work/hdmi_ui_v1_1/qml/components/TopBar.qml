import QtQuick 2.15
import QtQuick.Controls 2.15
import "../theme"

// App title + source badge (MOCK is prominent and always visible) + global
// state + RF parameters + page tabs.
Item {
    id: root
    property int currentPage: 0
    signal pageSelected(int index)

    implicitHeight: 56

    function sourceLabel() {
        return bridge.hasFrame ? bridge.frame.source : qsTr("—")
    }

    Row {
        id: leftGroup
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.gapSm

        Text {
            text: qsTr("RF AMR")
            color: Theme.accent
            font.pixelSize: Theme.h1
            font.weight: Font.Bold
            anchors.verticalCenter: parent.verticalCenter
        }

        // Source badge — MOCK is filled and prominent so simulated data is never
        // mistaken for live RF.
        Rectangle {
            height: 32
            radius: 16
            width: srcText.implicitWidth + 28
            color: sourceLabel() === "MOCK" ? Theme.mock : Theme.panelAlt
            anchors.verticalCenter: parent.verticalCenter
            Text {
                id: srcText
                anchors.centerIn: parent
                text: sourceLabel()
                color: sourceLabel() === "MOCK" ? Theme.mockText : Theme.text
                font.pixelSize: Theme.caption
                font.weight: Font.Bold
            }
        }

        Rectangle {
            visible: bridge.stale
            height: 32
            radius: 16
            width: 84
            color: Theme.warning
            anchors.verticalCenter: parent.verticalCenter
            Text {
                anchors.centerIn: parent
                text: qsTr("STALE")
                color: Theme.background
                font.pixelSize: Theme.caption
                font.weight: Font.Bold
            }
        }
    }

    Row {
        id: rightGroup
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.gap

        Text {
            text: bridge.hasFrame
                  ? qsTr("RF %1 GHz · %2 ksps · %3 fps")
                        .arg((bridge.frame.center_frequency_hz / 1e9).toFixed(3))
                        .arg((bridge.frame.sample_rate_hz / 1e3).toFixed(0))
                        .arg(bridge.frame.fps.toFixed(1))
                  : qsTr("RF — · — · —")
            color: Theme.textDim
            font.pixelSize: Theme.body
            anchors.verticalCenter: parent.verticalCenter
        }

        TabButton { label: qsTr("Main"); active: root.currentPage === 0; onClicked: root.pageSelected(0) }
        TabButton { label: qsTr("Diagnostics"); active: root.currentPage === 1; onClicked: root.pageSelected(1) }
    }
}
