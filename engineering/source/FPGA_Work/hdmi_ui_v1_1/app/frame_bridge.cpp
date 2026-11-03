#include "frame_bridge.hpp"

#include <chrono>

#include <QTime>

namespace hdmiui {
namespace {

constexpr int kStaleCheckMs = 250;
constexpr int kMaxEventLog = 200;

std::uint64_t steady_now_ns() {
    return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count());
}

QString wall_clock() {
    return QTime::currentTime().toString("HH:mm:ss.zzz");
}

}  // namespace

FrameBridge::FrameBridge(QObject* parent) : QObject(parent) {
    pollTimer_.setInterval(pollIntervalMs_);
    pollTimer_.setTimerType(Qt::CoarseTimer);
    connect(&pollTimer_, &QTimer::timeout, this, &FrameBridge::poll);

    staleTimer_.setInterval(kStaleCheckMs);
    staleTimer_.setTimerType(Qt::CoarseTimer);
    connect(&staleTimer_, &QTimer::timeout, this, &FrameBridge::checkStale);
}

FrameBridge::~FrameBridge() {
    stop();
}

void FrameBridge::setDataSource(std::unique_ptr<DataSource> src) {
    stop();
    src_ = std::move(src);
    seq_.reset();
    hasFrame_ = false;
    stale_ = false;
    firstFrame_ = true;
    loggedEnd_ = false;
    wasLowConfidence_ = false;
    haveLastClass_ = false;
    lastPredictedClass_.clear();
    lastArrivalNs_ = 0;
    lastSdr_ = Status::Unknown;
    lastFpga_ = Status::Unknown;
    lastNpu_ = Status::Unknown;
    lastDropped_ = lastOverflow_ = lastDuplicate_ = 0;
    lastReorder_ = lastTimeout_ = lastError_ = 0;
    frame_ = QVariantMap();
    sequence_ = QVariantMap();
    eventLog_.clear();
    emit frameChanged();
    emit sequenceChanged();
    emit staleChanged();
    emit eventLogChanged();
}

void FrameBridge::start() {
    stop();
    if (!src_) {
        log("error", "no data source selected");
        return;
    }
    firstFrame_ = true;
    loggedEnd_ = false;
    hasFrame_ = false;
    wasLowConfidence_ = false;
    stale_ = false;
    seq_.reset();
    haveLastClass_ = false;
    lastPredictedClass_.clear();
    lastSdr_ = Status::Unknown;
    lastFpga_ = Status::Unknown;
    lastNpu_ = Status::Unknown;
    lastDropped_ = lastOverflow_ = lastDuplicate_ = 0;
    lastReorder_ = lastTimeout_ = lastError_ = 0;
    frame_ = QVariantMap();
    sequence_ = QVariantMap();
    emit frameChanged();
    emit sequenceChanged();

    std::string err;
    if (!src_->open(&err)) {
        log("error", QString("open failed: %1").arg(QString::fromStdString(err)));
        return;
    }
    log("info", QString("source %1 (%2) opened")
                    .arg(QString::fromStdString(src_->name()),
                         QString::fromStdString(src_->kind())));
    emit staleChanged();
    pollTimer_.start();
    staleTimer_.start();
}

void FrameBridge::stop() {
    pollTimer_.stop();
    staleTimer_.stop();
    if (src_) src_->close();
}

void FrameBridge::poll() {
    if (!src_) return;
    const std::optional<ResultFrame> maybe = src_->next(pollIntervalMs_);
    if (maybe.has_value()) {
        applyFrame(*maybe);
    } else if (!src_->is_live() && !loggedEnd_) {
        // Mock and file sources are finite: nullopt means the stream finished.
        loggedEnd_ = true;
        log("info", "stream ended");
        pollTimer_.stop();
        // The staleness timer keeps running so the last frame dims in place.
    }
    // A live source (Unix socket) may return nullopt while still connecting or
    // idle; keep polling and let the staleness detector dim the last frame.
}

void FrameBridge::checkStale() {
    if (!hasFrame_) return;
    setStale(staleDetector_.is_stale(lastArrivalNs_, steady_now_ns()));
}

void FrameBridge::applyFrame(const ResultFrame& f) {
    // Consumer-side sequence integrity, independent of the producer counters.
    const SequenceStats before = seq_.stats();
    seq_.observe(f.frame_id);
    const SequenceStats after = seq_.stats();
    if (after.duplicate > before.duplicate)
        log("warning", QString("duplicate frame_id %1").arg(f.frame_id));
    else if (after.reorder > before.reorder)
        log("warning", QString("reordered frame_id %1").arg(f.frame_id));
    else if (after.dropped > before.dropped)
        log("warning", QString("sequence gap: %1 frame(s) dropped")
                           .arg(after.dropped - before.dropped));
    publishSequence();

    const bool low = f.confidence < lowConfidence_;

    if (firstFrame_) {
        firstFrame_ = false;
        log("info", QString("first frame #%1").arg(f.frame_id));
    } else if (haveLastClass_ && f.predicted_class != lastPredictedClass_) {
        log("info", QString("modulation %1 -> %2")
                        .arg(QString::fromStdString(lastPredictedClass_),
                             QString::fromStdString(f.predicted_class)));
    }

    if (low && !wasLowConfidence_)
        log("warning", QString("low confidence %1 (< %2)")
                           .arg(f.confidence, 0, 'f', 3)
                           .arg(lowConfidence_, 0, 'f', 2));
    wasLowConfidence_ = low;

    logStatus("SDR", f.sdr_status, lastSdr_);
    logStatus("FPGA", f.fpga_status, lastFpga_);
    logStatus("NPU", f.npu_status, lastNpu_);

    if (f.counters.dropped > lastDropped_)
        log("warning", QString("+%1 dropped").arg(f.counters.dropped - lastDropped_));
    if (f.counters.overflow > lastOverflow_)
        log("warning", QString("+%1 overflow").arg(f.counters.overflow - lastOverflow_));
    if (f.counters.duplicate > lastDuplicate_)
        log("warning", QString("+%1 duplicate").arg(f.counters.duplicate - lastDuplicate_));
    if (f.counters.reorder > lastReorder_)
        log("warning", QString("+%1 reorder").arg(f.counters.reorder - lastReorder_));
    if (f.counters.timeout > lastTimeout_)
        log("warning", QString("+%1 timeout").arg(f.counters.timeout - lastTimeout_));
    if (f.counters.error > lastError_)
        log("warning", QString("+%1 error").arg(f.counters.error - lastError_));

    lastArrivalNs_ = steady_now_ns();
    haveLastClass_ = true;
    lastPredictedClass_ = f.predicted_class;
    lastSdr_ = f.sdr_status;
    lastFpga_ = f.fpga_status;
    lastNpu_ = f.npu_status;
    lastDropped_ = f.counters.dropped;
    lastOverflow_ = f.counters.overflow;
    lastDuplicate_ = f.counters.duplicate;
    lastReorder_ = f.counters.reorder;
    lastTimeout_ = f.counters.timeout;
    lastError_ = f.counters.error;

    QVariantMap m;
    m["contract_version"] = f.contract_version;
    m["model_id"] = QString::fromStdString(f.model_id);
    m["frame_id"] = QVariant::fromValue<qulonglong>(f.frame_id);
    m["timestamp_ns"] = QVariant::fromValue<qulonglong>(f.timestamp_ns);
    m["source"] = QString::fromLatin1(source_name(f.source));
    QStringList cn;
    cn.reserve(static_cast<int>(f.class_names.size()));
    for (const std::string& c : f.class_names) cn.append(QString::fromStdString(c));
    m["class_names"] = cn;
    QVariantList scores;
    scores.reserve(static_cast<int>(f.scores.size()));
    for (double s : f.scores) scores.append(s);
    m["scores"] = scores;
    m["predicted_index"] = f.predicted_index;
    m["predicted_class"] = QString::fromStdString(f.predicted_class);
    m["confidence"] = f.confidence;
    m["low_confidence"] = low;
    m["snr_db"] = f.snr_db;
    m["center_frequency_hz"] = f.center_frequency_hz;
    m["sample_rate_hz"] = f.sample_rate_hz;
    m["fps"] = f.fps;

    QVariantMap lat;
    lat["sdr_capture"] = f.latency_us.sdr_capture;
    lat["resample_frame"] = f.latency_us.resample_frame;
    lat["plddr_transfer"] = f.latency_us.plddr_transfer;
    lat["fpga_process"] = f.latency_us.fpga_process;
    lat["npu_infer"] = f.latency_us.npu_infer;
    lat["end_to_end"] = f.latency_us.end_to_end;
    m["latency_us"] = lat;

    QVariantMap ctr;
    ctr["dropped"] = QVariant::fromValue<qulonglong>(f.counters.dropped);
    ctr["overflow"] = QVariant::fromValue<qulonglong>(f.counters.overflow);
    ctr["duplicate"] = QVariant::fromValue<qulonglong>(f.counters.duplicate);
    ctr["reorder"] = QVariant::fromValue<qulonglong>(f.counters.reorder);
    ctr["timeout"] = QVariant::fromValue<qulonglong>(f.counters.timeout);
    ctr["error"] = QVariant::fromValue<qulonglong>(f.counters.error);
    m["counters"] = ctr;

    m["sdr_status"] = QString::fromLatin1(status_name(f.sdr_status));
    m["fpga_status"] = QString::fromLatin1(status_name(f.fpga_status));
    m["npu_status"] = QString::fromLatin1(status_name(f.npu_status));

    QVariantList spec;
    spec.reserve(static_cast<int>(f.spectrum_bins.size()));
    for (double b : f.spectrum_bins) spec.append(b);
    m["spectrum_bins"] = spec;
    m["message"] = QString::fromStdString(f.message);

    frame_ = m;
    hasFrame_ = true;
    setStale(false);
    emit frameChanged();
}

void FrameBridge::publishSequence() {
    const SequenceStats& s = seq_.stats();
    QVariantMap m;
    m["seen"] = QVariant::fromValue<qulonglong>(s.seen);
    m["duplicate"] = QVariant::fromValue<qulonglong>(s.duplicate);
    m["reorder"] = QVariant::fromValue<qulonglong>(s.reorder);
    m["gap"] = QVariant::fromValue<qulonglong>(s.gap);
    m["dropped"] = QVariant::fromValue<qulonglong>(s.dropped);
    sequence_ = m;
    emit sequenceChanged();
}

void FrameBridge::setStale(bool s) {
    if (stale_ == s) return;
    stale_ = s;
    log(s ? "warning" : "info",
        s ? "no new frame within stale window" : "frame flow resumed");
    emit staleChanged();
}

void FrameBridge::log(const QString& level, const QString& text) {
    QVariantMap e;
    e["time"] = wall_clock();
    e["level"] = level;
    e["text"] = text;
    eventLog_.append(e);
    while (eventLog_.size() > kMaxEventLog) eventLog_.removeFirst();
    emit eventLogChanged();
}

void FrameBridge::logStatus(const char* name, Status now, Status prev) {
    if (prev == Status::Unknown || now == prev) return;
    log(now == Status::Ok ? "info" : "warning",
        QString("%1: %2 -> %3")
            .arg(QString::fromLatin1(name),
                 QString::fromLatin1(status_name(prev)),
                 QString::fromLatin1(status_name(now))));
}

}  // namespace hdmiui
