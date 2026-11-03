#pragma once
// Builds concrete DataSource objects and wires them into the FrameBridge, so the
// bridge stays generic (it only ever sees the abstract DataSource) and QML can
// switch sources through this thin controller.
#include <QObject>
#include <QStringList>
#include <memory>

#include "src/data_source.hpp"

namespace hdmiui {

class FrameBridge;

class SourceController : public QObject {
    Q_OBJECT
public:
    explicit SourceController(FrameBridge* bridge, QObject* parent = nullptr);

    Q_INVOKABLE QStringList mockScenarios() const;
    Q_INVOKABLE void startMock(const QString& scenario);
    Q_INVOKABLE void startFile(const QString& path);
    Q_INVOKABLE void startUnixSocket(const QString& path);
    Q_INVOKABLE void stop();

private:
    FrameBridge* bridge_;
};

}  // namespace hdmiui
