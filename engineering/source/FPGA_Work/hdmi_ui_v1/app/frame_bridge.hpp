#pragma once
// C++ <-> QML bridge.  Owns the DataSource, polls it, runs the consumer-side
// sequence monitor + staleness detector, and publishes a compact snapshot to
// QML via Q_PROPERTY bindings.  QML never sees the raw contract directly — it
// reads `frame`, `stale`, and `eventLog`.
#include <QObject>
#include <QTimer>
#include <QVariantList>
#include <QVariantMap>
#include <cstdint>
#include <memory>

#include "src/data_source.hpp"
#include "src/frame_validator.hpp"

namespace hdmiui {

class FrameBridge : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantMap frame READ frame NOTIFY frameChanged)
    Q_PROPERTY(bool stale READ stale NOTIFY staleChanged)
    Q_PROPERTY(bool hasFrame READ hasFrame NOTIFY frameChanged)
    Q_PROPERTY(QVariantList eventLog READ eventLog NOTIFY eventLogChanged)

public:
    explicit FrameBridge(QObject* parent = nullptr);
    ~FrameBridge() override;

    QVariantMap frame() const { return frame_; }
    bool stale() const { return stale_; }
    bool hasFrame() const { return hasFrame_; }
    QVariantList eventLog() const { return eventLog_; }

    void setDataSource(std::unique_ptr<DataSource> src);
    void setLowConfidenceThreshold(double v) { lowConfidence_ = v; }
    void setStaleTimeoutMs(int ms) {
        staleDetector_.set_timeout_ns(static_cast<std::uint64_t>(ms) * 1000000ULL);
    }
    void setPollIntervalMs(int ms) { pollIntervalMs_ = ms; }

    Q_INVOKABLE void start();
    Q_INVOKABLE void stop();

signals:
    void frameChanged();
    void staleChanged();
    void eventLogChanged();

private slots:
    void poll();
    void checkStale();

private:
    void applyFrame(const ResultFrame& f);
    void setStale(bool s);
    void log(const QString& level, const QString& text);
    void logStatus(const char* name, Status now, Status prev);

    std::unique_ptr<DataSource> src_;
    QTimer pollTimer_;
    QTimer staleTimer_;
    FrameSequenceMonitor seq_;
    StaleDetector staleDetector_{1500000000ULL};  // 1500 ms default
    double lowConfidence_ = 0.35;
    int pollIntervalMs_ = 66;

    QVariantMap frame_;
    QVariantList eventLog_;
    bool stale_ = false;
    bool hasFrame_ = false;
    bool loggedEnd_ = false;
    bool firstFrame_ = true;

    std::uint64_t lastTimestampNs_ = 0;
    std::uint64_t lastArrivalNs_ = 0;   // steady-clock arrival time; drives staleness
    int lastClassId_ = -1;
    bool wasLowConfidence_ = false;
    Status lastSdr_ = Status::Unknown;
    Status lastFpga_ = Status::Unknown;
    Status lastNpu_ = Status::Unknown;
    std::uint64_t lastDropped_ = 0, lastOverflow_ = 0, lastDuplicate_ = 0;
    std::uint64_t lastReorder_ = 0, lastTimeout_ = 0, lastError_ = 0;
};

}  // namespace hdmiui
