#include "unix_socket_data_source.hpp"

#include <chrono>

#include <QByteArray>
#include <QLocalSocket>
#include <QString>

#include "json_result_frame.hpp"

namespace hdmiui {
namespace {

constexpr int kReconnectMs = 500;   // min interval between connect attempts
constexpr int kConnectWaitMs = 30;  // per-attempt blocking connect wait

std::uint64_t steady_ms() {
    return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count());
}

}  // namespace

UnixSocketDataSource::UnixSocketDataSource(const std::string& socket_path)
    : path_(socket_path) {}

UnixSocketDataSource::~UnixSocketDataSource() {
    close();
}

bool UnixSocketDataSource::open(std::string* /*error*/) {
    opened_ = true;
    buf_.clear();
    error_ = 0;
    last_connect_ms_ = 0;
    // Never fail here: if the SDR adapter is absent the source stays
    // disconnected and retries, rather than crashing the UI.
    return true;
}

void UnixSocketDataSource::close() {
    opened_ = false;
    if (sock_) {
        sock_->disconnectFromServer();
        sock_.reset();
    }
    buf_.clear();
}

bool UnixSocketDataSource::connected() const {
    return sock_ && sock_->state() == QLocalSocket::ConnectedState;
}

void UnixSocketDataSource::ensure_connected() {
    if (connected()) return;
    const std::uint64_t now = steady_ms();
    if (now - last_connect_ms_ < static_cast<std::uint64_t>(kReconnectMs)) return;
    last_connect_ms_ = now;

    if (!sock_) sock_ = std::make_unique<QLocalSocket>();
    if (sock_->state() == QLocalSocket::ConnectingState) return;  // in flight
    sock_->connectToServer(QString::fromStdString(path_));
    sock_->waitForConnected(kConnectWaitMs);  // short blocking attempt
}

std::optional<ResultFrame> UnixSocketDataSource::parse_pending() {
    while (true) {
        std::string line;
        if (!buf_.pop_line(&line)) return std::nullopt;
        std::string err;
        std::optional<ResultFrame> f =
            parse_result_frame(QByteArray::fromStdString(line), &err);
        if (f) {
            if (error_ > 0) {
                f->counters.error += error_;
                error_ = 0;
            }
            return f;
        }
        error_++;  // malformed JSON line: count it, keep scanning
    }
}

std::optional<ResultFrame> UnixSocketDataSource::next(int timeout_ms) {
    if (!opened_) return std::nullopt;
    ensure_connected();
    if (!connected()) return std::nullopt;

    if (std::optional<ResultFrame> f = parse_pending()) return f;

    if (sock_->bytesAvailable() == 0) {
        if (!sock_->waitForReadyRead(timeout_ms)) {
            if (!connected()) sock_.reset();  // server went away: reconnect next call
            return std::nullopt;
        }
    }
    const QByteArray chunk = sock_->readAll();
    error_ += buf_.push(chunk.constData(), static_cast<std::size_t>(chunk.size()));
    return parse_pending();
}

}  // namespace hdmiui
