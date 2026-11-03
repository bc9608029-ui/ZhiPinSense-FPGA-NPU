#pragma once
// RESERVED — not implemented in this offline pass.
//
// The production data path is: SDR adapter (C++) streams ResultFrame JSON lines
// over a Unix domain socket -> this source -> UI.  It is intentionally left as
// a stub that fails loudly, so a wiring mistake is never mistaken for "working".
// Wire it to the real SDR adapter after the hardware arrives; the contract it
// consumes (contracts/result_frame.schema.json) is already final.
#include <optional>
#include <string>

#include "src/data_source.hpp"

namespace hdmiui {

class UnixSocketDataSource : public DataSource {
public:
    explicit UnixSocketDataSource(const std::string& socket_path) : path_(socket_path) {}

    std::string name() const override { return "SDR"; }
    std::string kind() const override { return "unix_socket"; }

    bool open(std::string* error) override {
        if (error) *error = "unix_socket source is reserved for the SDR adapter and is "
                            "not implemented in the offline UI pass (path: " + path_ + ")";
        return false;
    }

    std::optional<ResultFrame> next(int /*timeout_ms*/) override { return std::nullopt; }
    void close() override {}

private:
    std::string path_;
};

}  // namespace hdmiui
