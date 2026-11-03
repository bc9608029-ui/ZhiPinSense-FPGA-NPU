import QtQuick 2.15
import "../theme"

PanelFrame {
    title: qsTr("Spectrum")

    Item {
        id: content
        width: parent.width
        height: parent.height

        function bin(i) {
            if (!bridge.hasFrame) return 0
            var b = bridge.frame.spectrum_bins[i]
            return b === undefined ? 0 : b
        }

        // Flat bar spectrum: 128 bars, software-rendered cheaply.
        Repeater {
            model: 128

            Rectangle {
                x: index * (content.width / 128)
                width: Math.max(1, content.width / 128 - 1)
                height: Math.min(content.height, Math.max(2, content.bin(index) * content.height * 0.7))
                y: content.height - height
                color: Theme.accent
            }
        }
    }
}
