#include "source_controller.hpp"

#include <memory>

#include "app/frame_bridge.hpp"
#include "src/jsonlines_data_source.hpp"
#include "src/mock_data_source.hpp"
#include "src/unix_socket_data_source.hpp"

namespace hdmiui {

SourceController::SourceController(FrameBridge* bridge, QObject* parent)
    : QObject(parent), bridge_(bridge) {}

QStringList SourceController::mockScenarios() const {
    return {
        "normal", "modulation_switch", "low_confidence", "sdr_disconnect",
        "fpga_error", "npu_timeout", "drop_overflow", "recovery",
    };
}

void SourceController::startMock(const QString& scenario) {
    const std::string s = scenario.toStdString();
    MockDataSource::Scenario sc = MockDataSource::Scenario::Normal;
    for (int i = 0; i < 8; ++i) {
        const auto cand = static_cast<MockDataSource::Scenario>(i);
        if (s == MockDataSource::scenario_name(cand)) {
            sc = cand;
            break;
        }
    }
    bridge_->setDataSource(std::make_unique<MockDataSource>(sc));
    bridge_->start();
}

void SourceController::startFile(const QString& path) {
    bridge_->setDataSource(std::make_unique<JsonLinesDataSource>(path.toStdString()));
    bridge_->start();
}

void SourceController::startUnixSocket(const QString& path) {
    bridge_->setDataSource(std::make_unique<UnixSocketDataSource>(path.toStdString()));
    bridge_->start();
}

void SourceController::stop() {
    bridge_->stop();
}

}  // namespace hdmiui
