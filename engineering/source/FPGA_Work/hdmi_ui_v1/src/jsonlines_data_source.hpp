#pragma once
#include <cstdint>
#include <memory>
#include <optional>
#include <string>

#include "src/data_source.hpp"

class QFile;
class QTextStream;

namespace hdmiui {

// Reads a JSON-Lines file (one ResultFrame object per line).  Malformed lines
// are skipped and counted; the count is folded into the next valid frame's
// counters.error so the UI surfaces input corruption.
class JsonLinesDataSource : public DataSource {
public:
    explicit JsonLinesDataSource(const std::string& path);
    ~JsonLinesDataSource() override;

    std::string name() const override { return "FILE"; }
    std::string kind() const override { return "file"; }
    bool open(std::string* error) override;
    std::optional<ResultFrame> next(int timeout_ms) override;
    void close() override;

private:
    std::string path_;
    std::unique_ptr<QFile> file_;
    std::unique_ptr<QTextStream> stream_;
    std::uint64_t malformed_ = 0;
};

}  // namespace hdmiui
