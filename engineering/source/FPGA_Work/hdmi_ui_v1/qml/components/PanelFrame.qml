import QtQuick 2.15
import "../theme"

// A flat, bordered panel with an optional title.  Content is added as children
// and is laid out in the body area below the title (which fills the rest).
Rectangle {
    id: root
    color: Theme.panel
    border.color: Theme.border
    border.width: 1
    radius: Theme.radius

    property string title: ""
    default property alias content: body.data

    Text {
        id: titleText
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: Theme.gap
        anchors.rightMargin: Theme.gap
        anchors.topMargin: Theme.gap
        visible: root.title !== ""
        text: root.title
        color: Theme.textDim
        font.pixelSize: Theme.h1
        font.weight: Font.DemiBold
    }

    Item {
        id: body
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: titleText.visible ? titleText.bottom : parent.top
        anchors.bottom: parent.bottom
        anchors.margins: Theme.gap
        anchors.topMargin: Theme.gapSm
    }
}
