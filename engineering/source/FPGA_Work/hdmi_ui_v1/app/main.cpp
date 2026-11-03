// HDMI touch UI entry point.
//
// The UI runs either on the host (for development, with mock/file data) or on
// the FMQL30TAI board (HDMI output, touch input).  On the board the Zynq-7030
// PS has no GPU, so run with a software-rendered platform:
//
//     ./hdmi_ui_v1 -platform linuxfb
//     QT_QUICK_BACKEND=software ./hdmi_ui_v1 -platform eglfs   # if eglfs is built
//
// Data sources are switched from QML via the SourceController; the bridge
// never learns about a concrete source type.
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QUrl>

#include "app/frame_bridge.hpp"
#include "app/source_controller.hpp"
#include "contracts/result_frame.hpp"

int main(int argc, char* argv[]) {
    QGuiApplication app(argc, argv);
    app.setApplicationName("hdmi_ui_v1");
    app.setOrganizationName("fmsh");

    QQmlApplicationEngine engine;

    // The engine owns both objects (parented), which keeps them alive for the
    // lifetime of the QML scene and destroys them on teardown.
    auto* bridge = new hdmiui::FrameBridge(&engine);
    auto* controller = new hdmiui::SourceController(bridge, &engine);

    engine.rootContext()->setContextProperty("bridge", bridge);
    engine.rootContext()->setContextProperty("sourceController", controller);

    // The frozen class order lives in the contract; expose it read-only so QML
    // never re-declares it and the two can never drift apart.
    QStringList classNames;
    for (int i = 0; i < hdmiui::kNumClasses; ++i)
        classNames << QString::fromLatin1(hdmiui::class_names()[i]);
    engine.rootContext()->setContextProperty("classNames", classNames);

    engine.load(QUrl(QStringLiteral("qrc:/qml/Main.qml")));
    if (engine.rootObjects().isEmpty())
        return -1;

    // Start with a live mock feed so the UI is never blank on launch.
    controller->startMock(QStringLiteral("normal"));

    return app.exec();
}
