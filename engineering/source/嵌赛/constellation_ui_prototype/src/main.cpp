// main.cpp — entry point + QML backend (Controller) for the offline IQ
// constellation viewer. Pure offline: reads .ci16 / .f32 + JSON sidecars, plots
// REAL points, never fabricates demo data. No board / SDR / socket / live data.
#include "ConstellationItem.hpp"
#include "IqFrame.hpp"
#include "IqFrameLoader.hpp"

#include <QColor>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QGuiApplication>
#include <QImage>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointF>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickItem>
#include <QQuickWindow>
#include <QTextStream>
#include <QTimer>
#include <QUrl>
#include <QVector>
#include <QtQml/qqml.h>

#include <cmath>

namespace {

// Stage colors (suggested palette). Color is NEVER the only information source:
// the stage text and the legend are always shown too.
QColor stage_color(cst::Stage s) {
    switch (s) {
        case cst::Stage::RawRx:            return QColor(208, 212, 216);  // grey-white
        case cst::Stage::RecoveredPayload: return QColor(34, 195, 230);   // cyan
        case cst::Stage::ModelInput:       return QColor(61, 220, 132);   // green
        case cst::Stage::SymbolSampled:    return QColor(232, 201, 60);   // yellow
        default:                           return QColor(200, 200, 200);
    }
}
QColor outlier_color() { return QColor(229, 96, 95); }  // red (out-of-range)

QString fmt_freq(std::uint64_t hz) {
    if (hz >= 1000000) {
        const double mhz = static_cast<double>(hz) / 1000000.0;
        return QString::number(mhz, 'f', 2) + QStringLiteral(" MHz");
    }
    if (hz >= 1000) {
        const double khz = static_cast<double>(hz) / 1000.0;
        return QString::number(khz, 'f', 1) + QStringLiteral(" kHz");
    }
    return QString::number(hz) + QStringLiteral(" Hz");
}

}  // namespace

class Controller : public QObject {
    Q_OBJECT

    Q_PROPERTY(QString dataSource READ dataSource NOTIFY metricsChanged)
    Q_PROPERTY(QString stage READ stage NOTIFY metricsChanged)
    Q_PROPERTY(QString modulation READ modulation NOTIFY metricsChanged)
    Q_PROPERTY(QString predictedClass READ predictedClass NOTIFY metricsChanged)
    Q_PROPERTY(QString baselineClass READ baselineClass NOTIFY metricsChanged)
    Q_PROPERTY(bool agreement READ agreement NOTIFY metricsChanged)
    Q_PROPERTY(double confidence READ confidence NOTIFY metricsChanged)
    Q_PROPERTY(double cfoHz READ cfoHz NOTIFY metricsChanged)
    Q_PROPERTY(double sroPpm READ sroPpm NOTIFY metricsChanged)
    Q_PROPERTY(double d2RecScale READ d2RecScale NOTIFY metricsChanged)
    Q_PROPERTY(bool confidenceValid READ confidenceValid NOTIFY metricsChanged)
    Q_PROPERTY(bool cfoValid READ cfoValid NOTIFY metricsChanged)
    Q_PROPERTY(bool sroValid READ sroValid NOTIFY metricsChanged)
    Q_PROPERTY(bool gainValid READ gainValid NOTIFY metricsChanged)
    Q_PROPERTY(bool recoveryMetricsValid READ recoveryMetricsValid NOTIFY metricsChanged)
    Q_PROPERTY(QString metricProvenance READ metricProvenance NOTIFY metricsChanged)
    Q_PROPERTY(QString confidenceText READ confidenceText NOTIFY metricsChanged)
    Q_PROPERTY(QString cfoText READ cfoText NOTIFY metricsChanged)
    Q_PROPERTY(QString sroText READ sroText NOTIFY metricsChanged)
    Q_PROPERTY(QString gainText READ gainText NOTIFY metricsChanged)
    Q_PROPERTY(QString d2RecScaleText READ d2RecScaleText NOTIFY metricsChanged)
    Q_PROPERTY(QString sampleRateText READ sampleRateText NOTIFY metricsChanged)
    Q_PROPERTY(bool shaValid READ shaValid NOTIFY metricsChanged)
    Q_PROPERTY(bool timingValid READ timingValid NOTIFY metricsChanged)
    Q_PROPERTY(QString fileName READ fileName NOTIFY metricsChanged)
    Q_PROPERTY(qint64 frameId READ frameId NOTIFY metricsChanged)
    Q_PROPERTY(int pointCount READ pointCount NOTIFY metricsChanged)
    Q_PROPERTY(qint64 totalPoints READ totalPoints NOTIFY metricsChanged)
    Q_PROPERTY(QString sourceSha READ sourceSha NOTIFY metricsChanged)
    Q_PROPERTY(QString validationStatus READ validationStatus NOTIFY metricsChanged)
    Q_PROPERTY(QString coordinateMode READ coordinateMode NOTIFY coordinateChanged)
    Q_PROPERTY(double customRange READ customRange NOTIFY coordinateChanged)
    Q_PROPERTY(int pointLimit READ pointLimit NOTIFY coordinateChanged)
    Q_PROPERTY(bool paused READ paused NOTIFY playbackChanged)
    Q_PROPERTY(double playbackFps READ playbackFps NOTIFY playbackChanged)
    Q_PROPERTY(bool loop READ loop NOTIFY playbackChanged)
    Q_PROPERTY(QString errorText READ errorText NOTIFY metricsChanged)
    Q_PROPERTY(QString warning READ warning NOTIFY metricsChanged)
    Q_PROPERTY(double range READ range NOTIFY coordinateChanged)
    Q_PROPERTY(int outOfRangeCount READ outOfRangeCount NOTIFY metricsChanged)
    Q_PROPERTY(int frameIndex READ frameIndex NOTIFY metricsChanged)
    Q_PROPERTY(int frameCount READ frameCount NOTIFY frameCountChanged)

public:
    explicit Controller(QObject* parent = nullptr) : QObject(parent) {
        timer_.setSingleShot(false);
        connect(&timer_, &QTimer::timeout, this, &Controller::onTimer);
        applyPointLimit(pointLimit_);
    }

    void setPlot(ConstellationItem* p) { plot_ = p; }
    void setWindow(QQuickWindow* w) { window_ = w; }

    // ---- playback -----------------------------------------------------------
    Q_INVOKABLE bool openSidecar(const QUrl& url) {
        const QString path = url.isLocalFile() ? url.toLocalFile() : url.toString();
        sidecars_.clear();
        sidecars_.push_back(path.toStdString());
        current_ = 0;
        setPaused(true);
        emit frameCountChanged();
        return loadCurrent();
    }

    Q_INVOKABLE bool openDirectory(const QUrl& url) {
        const QString dir = url.isLocalFile() ? url.toLocalFile() : url.toString();
        std::string err;
        auto list = cst::list_sidecars(dir.toStdString(), err);
        if (list.empty()) {
            setError(QStringLiteral("目录中没有可用的 sidecar JSON: %1").arg(dir));
            return false;
        }
        sidecars_ = std::move(list);
        current_ = 0;
        setPaused(true);
        emit frameCountChanged();
        return loadCurrent();
    }

    Q_INVOKABLE void previousFrame() { step(-1); }
    Q_INVOKABLE void nextFrame() { step(+1); }

    Q_INVOKABLE void setPaused(bool p) {
        paused_ = p;
        if (paused_) stopTimer();
        else startTimer();
        emit playbackChanged();
    }
    Q_INVOKABLE void togglePause() { setPaused(!paused_); }

    // Error is persistent: it is NOT cleared by a subsequent successful load
    // (a normal status never silently overwrites an error). Dismiss explicitly.
    Q_INVOKABLE void clearError() {
        if (error_text_.isEmpty()) return;
        error_text_.clear();
        emit metricsChanged();
    }

    Q_INVOKABLE void setPlaybackFps(double fps) {
        playbackFps_ = std::max(0.1, fps);
        if (!paused_) startTimer();
        emit playbackChanged();
    }

    Q_INVOKABLE void setLoop(bool l) {
        loop_ = l;
        emit playbackChanged();
    }

    // ---- coordinate / point controls ---------------------------------------
    Q_INVOKABLE void setCoordinateMode(const QString& mode) {
        coordinateMode_ = mode;
        applyFrame();
        emit coordinateChanged();
        emit metricsChanged();
    }
    Q_INVOKABLE void setCustomRange(double r) {
        customRange_ = (r > 0.0 && std::isfinite(r)) ? r : 1.0;
        if (coordinateMode_ == QStringLiteral("CUSTOM")) applyFrame();
        emit coordinateChanged();
        emit metricsChanged();
    }
    Q_INVOKABLE void setPointLimit(int n) {
        applyPointLimit(n);
        applyFrame();
        emit coordinateChanged();
        emit metricsChanged();
    }

    // ---- export -------------------------------------------------------------
    Q_INVOKABLE QString screenshot(const QString& path) {
        if (!window_) return QStringLiteral("无窗口");
        QImage img = window_->grabWindow();
        if (img.isNull()) return QStringLiteral("截图失败");
        return img.save(path, "PNG") ? QString() : QStringLiteral("PNG 保存失败");
    }

    Q_INVOKABLE QString exportFrameJson(const QString& path) {
        QJsonObject o;
        o.insert(QStringLiteral("mode"), QStringLiteral("OFFLINE"));
        o.insert(QStringLiteral("stage"), QString::fromStdString(cst::stage_name(frame_.stage)));
        o.insert(QStringLiteral("source_sha256"), QString::fromStdString(frame_.payload_sha256));
        o.insert(QStringLiteral("frame_id"), static_cast<qint64>(frame_.frame_id));
        o.insert(QStringLiteral("modulation"), QString::fromStdString(frame_.modulation));
        o.insert(QStringLiteral("predicted_class"), QString::fromStdString(frame_.predicted_class));
        o.insert(QStringLiteral("baseline_class"), QString::fromStdString(frame_.baseline_class));
        o.insert(QStringLiteral("confidence"), frame_.confidence);
        o.insert(QStringLiteral("confidence_valid"), frame_.confidence_valid);
        o.insert(QStringLiteral("cfo_hz"), frame_.cfo_hz);
        o.insert(QStringLiteral("cfo_valid"), frame_.cfo_valid);
        o.insert(QStringLiteral("sro_ppm"), frame_.sro_ppm);
        o.insert(QStringLiteral("sro_valid"), frame_.sro_valid);
        o.insert(QStringLiteral("gain_mag"), frame_.gain_mag);
        o.insert(QStringLiteral("gain_valid"), frame_.gain_valid);
        o.insert(QStringLiteral("d2_rec_scale"), frame_.d2_rec_scale);
        o.insert(QStringLiteral("recovery_metrics_valid"), frame_.recovery_metrics_valid);
        o.insert(QStringLiteral("metric_provenance"), QString::fromStdString(frame_.metric_provenance));
        o.insert(QStringLiteral("sample_rate_hz"), static_cast<qint64>(frame_.sample_rate_hz));
        o.insert(QStringLiteral("complex_count"), static_cast<qint64>(frame_.complex_count));
        o.insert(QStringLiteral("displayed_points"), static_cast<int>(disp_i_.size()));
        o.insert(QStringLiteral("coordinate_mode"), coordinateMode_);
        o.insert(QStringLiteral("range"), range_);
        o.insert(QStringLiteral("out_of_range_points"), out_of_range_);
        o.insert(QStringLiteral("iq_file"), QString::fromStdString(frame_.iq_file));
        o.insert(QStringLiteral("source_path"), QString::fromStdString(frame_.source_path));
        QFile f(path);
        if (!f.open(QIODevice::WriteOnly)) return QStringLiteral("无法写入: %1").arg(path);
        f.write(QJsonDocument(o).toJson(QJsonDocument::Indented));
        return QString();
    }

    Q_INVOKABLE QString exportCsv(const QString& path) {
        QFile f(path);
        if (!f.open(QIODevice::WriteOnly)) return QStringLiteral("无法写入: %1").arg(path);
        QTextStream ts(&f);
        ts << "index,I,Q,out_of_range\n";
        for (int k = 0; k < static_cast<int>(disp_i_.size()); ++k) {
            ts << k << ',' << disp_i_[k] << ',' << disp_q_[k] << ','
               << (disp_oor_[k] ? 1 : 0) << '\n';
        }
        return QString();
    }

    Q_INVOKABLE QString exportDiagnostic(const QString& path) {
        QFile f(path);
        if (!f.open(QIODevice::WriteOnly)) return QStringLiteral("无法写入: %1").arg(path);
        QTextStream ts(&f);
        ts << "M29 RML23 constellation UI — offline diagnostic\n";
        ts << "mode=OFFLINE\n";
        ts << "stage=" << cst::stage_name(frame_.stage) << '\n';
        ts << "source_sha256=" << frame_.payload_sha256.c_str() << '\n';
        ts << "frame_id=" << frame_.frame_id << '\n';
        ts << "modulation=" << frame_.modulation.c_str() << '\n';
        ts << "predicted_class=" << frame_.predicted_class.c_str() << '\n';
        ts << "baseline_class=" << frame_.baseline_class.c_str() << '\n';
        ts << "agreement=" << (frame_.prediction_agreement() ? "true" : "false") << '\n';
        ts << "confidence=" << frame_.confidence << '\n';
        ts << "confidence_valid=" << (frame_.confidence_valid ? "true" : "false") << '\n';
        ts << "cfo_hz=" << frame_.cfo_hz << '\n';
        ts << "cfo_valid=" << (frame_.cfo_valid ? "true" : "false") << '\n';
        ts << "sro_ppm=" << frame_.sro_ppm << '\n';
        ts << "sro_valid=" << (frame_.sro_valid ? "true" : "false") << '\n';
        ts << "gain_mag=" << frame_.gain_mag << '\n';
        ts << "gain_valid=" << (frame_.gain_valid ? "true" : "false") << '\n';
        ts << "d2_rec_scale=" << frame_.d2_rec_scale << '\n';
        ts << "recovery_metrics_valid=" << (frame_.recovery_metrics_valid ? "true" : "false") << '\n';
        ts << "metric_provenance=" << frame_.metric_provenance.c_str() << '\n';
        ts << "sample_rate_hz=" << frame_.sample_rate_hz << '\n';
        ts << "complex_count=" << frame_.complex_count << '\n';
        ts << "displayed_points=" << disp_i_.size() << '\n';
        ts << "coordinate_mode=" << coordinateMode_.toStdString().c_str() << '\n';
        ts << "range=" << range_ << '\n';
        ts << "out_of_range_points=" << out_of_range_ << '\n';
        ts << "symbol_timing_valid=" << (frame_.symbol_timing_valid ? "true" : "false")
           << '\n';
        return QString();
    }

    // ---- property getters ---------------------------------------------------
    QString dataSource() const { return QStringLiteral("离线文件"); }
    QString stage() const { return QString::fromLatin1(cst::stage_name(frame_.stage)); }
    QString modulation() const { return QString::fromStdString(frame_.modulation); }
    QString predictedClass() const { return QString::fromStdString(frame_.predicted_class); }
    QString baselineClass() const { return QString::fromStdString(frame_.baseline_class); }
    bool agreement() const { return frame_.prediction_agreement(); }
    double confidence() const { return frame_.confidence; }
    double cfoHz() const { return frame_.cfo_hz; }
    double sroPpm() const { return frame_.sro_ppm; }
    double d2RecScale() const { return frame_.d2_rec_scale; }
    bool confidenceValid() const { return frame_.confidence_valid; }
    bool cfoValid() const { return frame_.cfo_valid; }
    bool sroValid() const { return frame_.sro_valid; }
    bool gainValid() const { return frame_.gain_valid; }
    bool recoveryMetricsValid() const { return frame_.recovery_metrics_valid; }
    QString metricProvenance() const { return QString::fromStdString(frame_.metric_provenance); }

    // Display text: invalid/unavailable metrics are shown as Chinese "占位/不可用"
    // or "不可用", never as a numeric value (a raw 0 must not mean "measured 0").
    QString confidenceText() const {
        return frame_.confidence_valid
            ? QString::number(frame_.confidence, 'f', 3)
            : QStringLiteral("占位/不可用");
    }
    QString cfoText() const {
        return frame_.cfo_valid
            ? QString::number(frame_.cfo_hz, 'f', 1) + QStringLiteral(" Hz")
            : QStringLiteral("不可用");
    }
    QString sroText() const {
        return frame_.sro_valid
            ? QString::number(frame_.sro_ppm, 'f', 3) + QStringLiteral(" ppm")
            : QStringLiteral("不可用");
    }
    QString gainText() const {
        return frame_.gain_valid
            ? QString::number(frame_.gain_mag, 'f', 4)
            : QStringLiteral("不可用");
    }
    QString d2RecScaleText() const {
        return (frame_.recovery_metrics_valid && frame_.d2_rec_scale > 0.0)
            ? QString::number(frame_.d2_rec_scale, 'f', 6)
            : QString();
    }
    QString sampleRateText() const { return fmt_freq(frame_.sample_rate_hz); }
    bool shaValid() const { return sha_valid_; }
    bool timingValid() const { return frame_.symbol_timing_valid; }
    QString fileName() const { return QString::fromStdString(frame_.iq_file); }
    qint64 frameId() const { return static_cast<qint64>(frame_.frame_id); }
    int pointCount() const { return static_cast<int>(disp_i_.size()); }
    qint64 totalPoints() const { return static_cast<qint64>(frame_.complex_count); }
    QString sourceSha() const { return QString::fromStdString(frame_.payload_sha256); }
    QString validationStatus() const { return validation_status_; }
    QString coordinateMode() const { return coordinateMode_; }
    double customRange() const { return customRange_; }
    int pointLimit() const { return pointLimit_; }
    bool paused() const { return paused_; }
    double playbackFps() const { return playbackFps_; }
    bool loop() const { return loop_; }
    QString errorText() const { return error_text_; }
    QString warning() const { return warning_; }
    double range() const { return range_; }
    int outOfRangeCount() const { return out_of_range_; }
    int frameIndex() const { return sidecars_.empty() ? 0 : current_ + 1; }
    int frameCount() const { return static_cast<int>(sidecars_.size()); }

signals:
    void metricsChanged();
    void coordinateChanged();
    void playbackChanged();
    void frameCountChanged();

private:
    void applyPointLimit(int n) {
        pointLimit_ = (n <= 0) ? 4096 : std::min(n, 4096);
    }

    void startTimer() {
        if (sidecars_.size() <= 1 && !loop_) return;
        timer_.start(static_cast<int>(1000.0 / playbackFps_));
    }
    void stopTimer() { timer_.stop(); }

    void onTimer() { step(+1); }

    void step(int delta) {
        if (sidecars_.empty()) return;
        const int n = static_cast<int>(sidecars_.size());
        int next = current_ + delta;
        if (next < 0) next = loop_ ? n - 1 : 0;
        if (next >= n) {
            if (!loop_) { setPaused(true); return; }
            next = 0;
        }
        current_ = next;
        loadCurrent();
    }

    void setError(const QString& e) {
        error_text_ = e;
        emit metricsChanged();
    }

    bool loadCurrent() {
        warning_.clear();
        if (current_ < 0 || current_ >= static_cast<int>(sidecars_.size())) return false;

        cst::IqFrame f;
        std::string err;
        if (!cst::load_sidecar_frame(sidecars_[current_], f, err)) {
            validation_status_.clear();   // no green "valid" text alongside an error
            setError(QStringLiteral("帧加载失败（已停止）: %1").arg(QString::fromStdString(err)));
            setPaused(true);   // corrupted frame STOPS playback, never auto-skips
            emit metricsChanged();
            return false;
        }

        // Warn on duplicate / regressing frame_id during sequential playback.
        if (has_prev_ && f.frame_id <= prev_frame_id_) {
            warning_ = QStringLiteral("警告：frame_id 未递增（前一帧 %1，当前 %2）")
                           .arg(prev_frame_id_)
                           .arg(f.frame_id);
        }
        prev_frame_id_ = f.frame_id;
        has_prev_ = true;

        frame_ = std::move(f);
        sha_valid_ = true;
        validation_status_ = QStringLiteral("已通过校验（长度/SHA/dtype/layout）");
        applyFrame();
        emit metricsChanged();
        return true;
    }

    void applyFrame() {
        if (frame_.i.empty()) return;

        // Deterministic decimation (C++, never QML JS).
        const auto idx = cst::decimate_indices(frame_.i.size(),
                                               static_cast<std::size_t>(pointLimit_));
        disp_i_.clear();
        disp_q_.clear();
        disp_i_.reserve(idx.size());
        disp_q_.reserve(idx.size());
        for (std::size_t k : idx) {
            disp_i_.push_back(frame_.i[k]);
            disp_q_.push_back(frame_.q[k]);
        }

        // Range: AUTO (robust quantile) / FIXED_1 / FIXED_2 / CUSTOM.
        double r = 1.0;
        if (coordinateMode_ == QStringLiteral("AUTO")) {
            std::size_t oor = 0;
            r = cst::auto_scale_range(frame_.i, frame_.q, oor);
        } else if (coordinateMode_ == QStringLiteral("FIXED_1")) {
            r = 1.0;
        } else if (coordinateMode_ == QStringLiteral("FIXED_2")) {
            r = 2.0;
        } else {  // CUSTOM
            r = customRange_;
        }
        range_ = r;

        // Transform + colors + out-of-range flags (single C++ pass).
        std::vector<float> ux, uy;
        cst::transform_to_unit(disp_i_, disp_q_, static_cast<float>(r), ux, uy);
        out_of_range_ = 0;
        disp_oor_.assign(disp_i_.size(), false);

        QVector<QPointF> pts;
        QVector<QColor> colors;
        pts.reserve(static_cast<int>(disp_i_.size()));
        colors.reserve(static_cast<int>(disp_i_.size()));
        const QColor sc = stage_color(frame_.stage);
        for (std::size_t k = 0; k < disp_i_.size(); ++k) {
            const bool oor = (std::fabs(disp_i_[k]) > r || std::fabs(disp_q_[k]) > r);
            pts.append(QPointF(static_cast<double>(ux[k]), static_cast<double>(uy[k])));
            if (oor) {
                ++out_of_range_;
                disp_oor_[k] = true;
                colors.append(outlier_color());
            } else {
                colors.append(sc);
            }
        }
        if (plot_) plot_->setPoints(pts, colors);
    }

    ConstellationItem* plot_ = nullptr;
    QQuickWindow* window_ = nullptr;

    cst::IqFrame frame_;
    bool sha_valid_ = false;
    QString validation_status_;
    QString error_text_;
    QString warning_;
    bool has_prev_ = false;
    std::uint64_t prev_frame_id_ = 0;

    std::vector<float> disp_i_, disp_q_;
    std::vector<bool> disp_oor_;
    double range_ = 1.0;
    int out_of_range_ = 0;

    std::vector<std::string> sidecars_;
    int current_ = 0;

    QString coordinateMode_ = QStringLiteral("AUTO");
    double customRange_ = 1.0;
    int pointLimit_ = 4096;
    bool paused_ = false;
    double playbackFps_ = 1.0;
    bool loop_ = false;

    QTimer timer_;
};

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    app.setOrganizationName(QStringLiteral("offline-prototype"));
    app.setApplicationName(QStringLiteral("M29 RML23 constellation viewer"));

    qmlRegisterType<ConstellationItem>("Constellation", 1, 0, "ConstellationItem");

    // CLI: --fixture-dir DIR [--fps N] [--loop] | --sidecar FILE
    QStringList args = app.arguments();
    QString sidecar;
    QString fixtureDir;
    double fps = 1.0;
    bool loop = false;
    for (int i = 1; i < args.size(); ++i) {
        const QString a = args.at(i);
        if (a == QLatin1String("--sidecar") && i + 1 < args.size()) sidecar = args.at(++i);
        else if (a == QLatin1String("--fixture-dir") && i + 1 < args.size()) fixtureDir = args.at(++i);
        else if (a == QLatin1String("--fps") && i + 1 < args.size()) fps = args.at(++i).toDouble();
        else if (a == QLatin1String("--loop")) loop = true;
    }

    QQmlApplicationEngine engine;
    Controller controller;
    engine.rootContext()->setContextProperty(QStringLiteral("controller"), &controller);
    engine.load(QUrl(QStringLiteral("qrc:/qml/Main.qml")));
    if (engine.rootObjects().isEmpty()) return 1;

    QQuickWindow* win = qobject_cast<QQuickWindow*>(engine.rootObjects().value(0));
    ConstellationItem* plot = nullptr;
    if (win) {
        plot = win->findChild<ConstellationItem*>(QStringLiteral("constellationPlot"));
    }
    controller.setPlot(plot);
    controller.setWindow(win);
    controller.setPlaybackFps(fps);
    controller.setLoop(loop);

    if (!sidecar.isEmpty()) {
        controller.openSidecar(QUrl::fromLocalFile(sidecar));
    } else if (!fixtureDir.isEmpty()) {
        controller.openDirectory(QUrl::fromLocalFile(fixtureDir));
    }

    return app.exec();
}

#include "main.moc"
