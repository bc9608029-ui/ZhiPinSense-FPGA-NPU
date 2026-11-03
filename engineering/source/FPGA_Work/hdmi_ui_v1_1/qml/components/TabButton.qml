import QtQuick 2.15
import QtQuick.Controls 2.15
import "../theme"

// A flat page-tab button with a highlighted "active" state.
Button {
    id: control
    property string label: ""
    property bool active: false

    implicitHeight: 40
    leftPadding: Theme.gap
    rightPadding: Theme.gap

    contentItem: Text {
        text: control.label
        color: control.active ? Theme.background : Theme.text
        font.pixelSize: Theme.body
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        color: control.active ? Theme.accent : Theme.panelAlt
        border.color: Theme.border
        border.width: 1
        radius: Theme.radius
    }
}
