#include "jsonlines_data_source.hpp"

#include <QFile>
#include <QTextStream>

#include "src/json_result_frame.hpp"

namespace hdmiui {

JsonLinesDataSource::JsonLinesDataSource(const std::string& path) : path_(path) {}

JsonLinesDataSource::~JsonLinesDataSource() = default;

bool JsonLinesDataSource::open(std::string* error) {
    file_ = std::make_unique<QFile>(QString::fromStdString(path_));
    if (!file_->open(QIODevice::ReadOnly | QIODevice::Text)) {
        if (error) *error = "cannot open " + path_ + ": " + file_->errorString().toStdString();
        file_.reset();
        return false;
    }
    stream_ = std::make_unique<QTextStream>(file_.get());
    stream_->setCodec("UTF-8");
    malformed_ = 0;
    return true;
}

void JsonLinesDataSource::close() {
    stream_.reset();
    if (file_) file_->close();
    file_.reset();
}

std::optional<ResultFrame> JsonLinesDataSource::next(int /*timeout_ms*/) {
    if (!file_ || !stream_) return std::nullopt;
    while (!stream_->atEnd()) {
        const QString line = stream_->readLine();
        if (line.trimmed().isEmpty()) continue;
        std::string err;
        std::optional<ResultFrame> f = parse_result_frame(line.toUtf8(), &err);
        if (f.has_value()) {
            if (malformed_ > 0) {
                f->counters.error += malformed_;
                if (f->message.empty()) f->message = "input: " + std::to_string(malformed_) + " malformed line(s) skipped";
                malformed_ = 0;
            }
            return f;
        }
        malformed_++;
    }
    return std::nullopt;  // EOF
}

}  // namespace hdmiui
