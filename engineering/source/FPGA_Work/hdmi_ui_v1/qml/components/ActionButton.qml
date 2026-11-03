import QtQuick 2.15
import QtQuick.Controls 2.15
import "../theme"

// Flat touch button matching the panel theme (48 px target).
Button {
    id: control
    implicitHeight: Theme.touch
    leftPadding: Theme.gap
    rightPadding: Theme.gap

    contentItem: Text {
        text: control.text
        color: control.enabled ? Theme.text : Theme.textDim
        font.pixelSize: Theme.body
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        color: control.pressed ? Theme.panelAlt : Theme.panel
        border.color: control.pressed ? Theme.accent : Theme.border
        border.width: 1
        radius: Theme.radius
    }
}
