import QtQuick 2.15
import Constellation 1.0

// ConstellationPlot.qml — the actual plot area. Static QML draws the grid, the
// centered axes, the origin marker and the axis labels; the high-frequency
// points are drawn by the C++ ConstellationItem scene-graph node (never a Canvas,
// never per-point QML objects). The scatter is letterboxed into the largest
// centered square so I and Q share one scale with the origin centered.
Rectangle {
    id: root
    property QtObject theme: null
    property string rangeLabel: controller.range.toFixed(2)

    color: theme.plotBackground
    border.color: theme.border
    border.width: 1

    Item {
        id: square
        readonly property real side: Math.min(root.width, root.height)
        x: (root.width - side) / 2
        y: (root.height - side) / 2
        width: side
        height: side

        // Vertical grid lines (11 lines at 10% steps; the center one is the axis).
        Repeater {
            model: 11
            delegate: Rectangle {
                x: index * square.width / 10
                y: 0
                width: 1
                height: square.height
                color: index === 5 ? (theme ? theme.axisLine : "#3A4152")
                                   : (theme ? theme.gridLine : "#232833")
            }
        }
        // Horizontal grid lines.
        Repeater {
            model: 11
            delegate: Rectangle {
                y: index * square.height / 10
                x: 0
                width: square.width
                height: 1
                color: index === 5 ? (theme ? theme.axisLine : "#3A4152")
                                   : (theme ? theme.gridLine : "#232833")
            }
        }
        // Origin marker.
        Rectangle {
            x: square.width / 2 - 3
            y: square.height / 2 - 3
            width: 6
            height: 6
            color: theme.textFaint
        }

        // C++ scene-graph scatter (objectName is how the Controller pushes points).
        ConstellationItem {
            id: plot
            objectName: "constellationPlot"
            anchors.fill: parent
            pointSize: 2
        }

        // I-axis labels (bottom edge).
        Text {
            anchors.left: parent.left
            anchors.leftMargin: 4
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 2
            text: "-" + rangeLabel
            color: theme.textFaint
            font.pixelSize: theme.fontSizeSmall
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 2
            text: "0"
            color: theme.textFaint
            font.pixelSize: theme.fontSizeSmall
        }
        Text {
            anchors.right: parent.right
            anchors.rightMargin: 4
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 2
            text: "+" + rangeLabel
            color: theme.textFaint
            font.pixelSize: theme.fontSizeSmall
        }
        // Q-axis labels (left edge).
        Text {
            anchors.left: parent.left
            anchors.leftMargin: 4
            anchors.top: parent.top
            anchors.topMargin: 2
            text: "+" + rangeLabel
            color: theme.textFaint
            font.pixelSize: theme.fontSizeSmall
        }
        Text {
            anchors.left: parent.left
            anchors.leftMargin: 4
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 16
            text: "-" + rangeLabel
            color: theme.textFaint
            font.pixelSize: theme.fontSizeSmall
        }
    }
}
