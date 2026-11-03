#include "json_result_frame.hpp"

#include <cmath>
#include <limits>

#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QStringList>

namespace hdmiui {
namespace {

bool finite_double(const QJsonValue& v, double* out) {
    if (!v.isDouble()) return false;
    const double d = v.toDouble();
    if (!std::isfinite(d)) return false;
    *out = d;
    return true;
}

double num(const QJsonValue& v, double def = 0.0) {
    double out = def;
    finite_double(v, &out);
    return out;
}

std::uint64_t unum(const QJsonValue& v, std::uint64_t def = 0) {
    double out = 0.0;
    if (finite_double(v, &out) && out >= 0.0 && out <= 9.007199254740992e15)
        return static_cast<std::uint64_t>(out);
    return def;
}

// A small integer stored as a JSON number.  Returns `def` when missing or
// out of int range so validate() can flag it.
int inum(const QJsonValue& v, int def = -1) {
    double out = 0.0;
    if (finite_double(v, &out) && out >= -2147483648.0 && out <= 2147483647.0)
        return static_cast<int>(out);
    return def;
}

std::vector<double> num_array(const QJsonValue& v) {
    std::vector<double> out;
    if (!v.isArray()) return out;
    const QJsonArray a = v.toArray();
    out.reserve(static_cast<std::size_t>(a.size()));
    for (const QJsonValue& e : a) {
        if (e.isDouble()) out.push_back(e.toDouble());
        else out.push_back(std::numeric_limits<double>::quiet_NaN());
    }
    return out;
}

std::vector<std::string> str_array(const QJsonValue& v) {
    std::vector<std::string> out;
    if (!v.isArray()) return out;
    const QJsonArray a = v.toArray();
    out.reserve(static_cast<std::size_t>(a.size()));
    for (const QJsonValue& e : a)
        out.push_back(e.toString().toStdString());
    return out;
}

// Fill the fields shared by both shapes.
void fill_common(ResultFrame& f, const QJsonObject& o) {
    f.frame_id = unum(o.value("frame_id"));
    f.timestamp_ns = unum(o.value("timestamp_ns"));
    f.source = source_from_name(o.value("source").toString().toStdString());
    f.confidence = num(o.value("confidence"), std::numeric_limits<double>::quiet_NaN());
    f.snr_db = num(o.value("snr_db"), std::numeric_limits<double>::quiet_NaN());
    f.center_frequency_hz = num(o.value("center_frequency_hz"));
    f.sample_rate_hz = num(o.value("sample_rate_hz"));
    f.fps = num(o.value("fps"));
    f.sdr_status = status_from_name(o.value("sdr_status").toString().toStdString());
    f.fpga_status = status_from_name(o.value("fpga_status").toString().toStdString());
    f.npu_status = status_from_name(o.value("npu_status").toString().toStdString());
    f.spectrum_bins = num_array(o.value("spectrum_bins"));
    f.message = o.value("message").toString().toStdString();

    if (o.value("latency_us").isObject()) {
        const QJsonObject l = o.value("latency_us").toObject();
        f.latency_us.sdr_capture = num(l.value("sdr_capture"));
        f.latency_us.resample_frame = num(l.value("resample_frame"));
        f.latency_us.plddr_transfer = num(l.value("plddr_transfer"));
        f.latency_us.fpga_process = num(l.value("fpga_process"));
        f.latency_us.npu_infer = num(l.value("npu_infer"));
        f.latency_us.end_to_end = num(l.value("end_to_end"));
    }

    if (o.value("counters").isObject()) {
        const QJsonObject c = o.value("counters").toObject();
        f.counters.dropped = unum(c.value("dropped"));
        f.counters.overflow = unum(c.value("overflow"));
        f.counters.duplicate = unum(c.value("duplicate"));
        f.counters.reorder = unum(c.value("reorder"));
        f.counters.timeout = unum(c.value("timeout"));
        f.counters.error = unum(c.value("error"));
    }
}

// V1.1 shape: contract_version / model_id / class_names / scores /
// predicted_index / predicted_class.
std::optional<ResultFrame> parse_v1_1(const QJsonObject& o) {
    ResultFrame f;
    f.contract_version = inum(o.value("contract_version"), -1);
    f.model_id = o.value("model_id").toString().toStdString();
    f.class_names = str_array(o.value("class_names"));
    f.scores = num_array(o.value("scores"));
    f.predicted_index = inum(o.value("predicted_index"), -1);
    f.predicted_class = o.value("predicted_class").toString().toStdString();
    fill_common(f, o);
    return f;
}

// Legacy V1 shape: schema_version / class_id / class_name / probabilities.
std::optional<ResultFrame> parse_legacy(const QJsonObject& o) {
    ResultFrame f;
    f.contract_version = inum(o.value("schema_version"), -1);
    f.model_id = "";
    f.class_names = legacy_class_names();
    f.scores = num_array(o.value("probabilities"));
    f.predicted_index = inum(o.value("class_id"), -1);
    f.predicted_class = o.value("class_name").toString().toStdString();
    fill_common(f, o);
    return f;
}

}  // namespace

std::optional<ResultFrame> parse_result_frame(const QByteArray& line, std::string* error) {
    QJsonParseError perr{};
    const QJsonDocument doc = QJsonDocument::fromJson(line, &perr);
    if (perr.error != QJsonParseError::NoError) {
        if (error) *error = "json parse: " + perr.errorString().toStdString();
        return std::nullopt;
    }
    if (!doc.isObject()) {
        if (error) *error = "json: root is not an object";
        return std::nullopt;
    }
    const QJsonObject o = doc.object();

    std::optional<ResultFrame> f;
    if (o.contains("contract_version")) f = parse_v1_1(o);
    else if (o.contains("schema_version")) f = parse_legacy(o);
    else {
        if (error) *error = "json: missing contract_version (and legacy schema_version)";
        return std::nullopt;
    }

    const std::string reason = validate(*f);
    if (!reason.empty()) {
        if (error) *error = "invalid frame: " + reason;
        return std::nullopt;
    }
    return f;
}

QByteArray to_json(const ResultFrame& f) {
    QJsonObject o;
    o["contract_version"] = f.contract_version;
    o["model_id"] = QString::fromStdString(f.model_id);
    o["frame_id"] = static_cast<double>(f.frame_id);
    o["timestamp_ns"] = static_cast<double>(f.timestamp_ns);
    o["source"] = source_name(f.source);
    QJsonArray cn;
    for (const std::string& c : f.class_names) cn.append(QString::fromStdString(c));
    o["class_names"] = cn;
    QJsonArray sc;
    for (double s : f.scores) sc.append(s);
    o["scores"] = sc;
    o["predicted_index"] = f.predicted_index;
    o["predicted_class"] = QString::fromStdString(f.predicted_class);
    o["confidence"] = f.confidence;
    o["snr_db"] = f.snr_db;
    o["center_frequency_hz"] = f.center_frequency_hz;
    o["sample_rate_hz"] = f.sample_rate_hz;
    QJsonObject l;
    l["sdr_capture"] = f.latency_us.sdr_capture;
    l["resample_frame"] = f.latency_us.resample_frame;
    l["plddr_transfer"] = f.latency_us.plddr_transfer;
    l["fpga_process"] = f.latency_us.fpga_process;
    l["npu_infer"] = f.latency_us.npu_infer;
    l["end_to_end"] = f.latency_us.end_to_end;
    o["latency_us"] = l;
    o["fps"] = f.fps;
    QJsonObject c;
    c["dropped"] = static_cast<double>(f.counters.dropped);
    c["overflow"] = static_cast<double>(f.counters.overflow);
    c["duplicate"] = static_cast<double>(f.counters.duplicate);
    c["reorder"] = static_cast<double>(f.counters.reorder);
    c["timeout"] = static_cast<double>(f.counters.timeout);
    c["error"] = static_cast<double>(f.counters.error);
    o["counters"] = c;
    o["sdr_status"] = status_name(f.sdr_status);
    o["fpga_status"] = status_name(f.fpga_status);
    o["npu_status"] = status_name(f.npu_status);
    if (!f.spectrum_bins.empty()) {
        QJsonArray b;
        for (double x : f.spectrum_bins) b.append(x);
        o["spectrum_bins"] = b;
    }
    if (!f.message.empty()) o["message"] = QString::fromStdString(f.message);
    return QJsonDocument(o).toJson(QJsonDocument::Compact);
}

}  // namespace hdmiui
