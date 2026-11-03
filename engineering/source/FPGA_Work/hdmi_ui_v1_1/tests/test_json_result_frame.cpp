// Qt-dependent JSON parse test: V1.1 shape, legacy V1 shape, malformed input,
// missing version, and a to_json round-trip.  Requires Qt5::Core (QJsonDocument).
// Mirrors tests/test_json_result_frame.py.

#include <cstdint>
#include <cstdio>
#include <string>

#include "src/json_result_frame.hpp"

using namespace hdmiui;

namespace {
int g_failures = 0;

void check(bool ok, const char* what) {
    if (!ok) {
        std::fprintf(stderr, "FAIL: %s\n", what);
        ++g_failures;
    }
}
}  // namespace

int main() {
    const char* v11 = R"({
      "contract_version": 2, "model_id": "m",
      "frame_id": 5, "timestamp_ns": 1, "source": "MOCK",
      "class_names": ["AM-DSB","WBFM","2FSK","GFSK","BPSK","QPSK","8PSK","16QAM","64QAM","OFDM"],
      "scores": [0.01,0.01,0.01,0.01,0.01,0.01,0.01,0.9,0.02,0.01],
      "predicted_index": 7, "predicted_class": "16QAM", "confidence": 0.9,
      "snr_db": 18.0, "center_frequency_hz": 2400000000.0, "sample_rate_hz": 128000.0,
      "latency_us": {"sdr_capture":1,"resample_frame":1,"plddr_transfer":1,"fpga_process":1,"npu_infer":1,"end_to_end":5},
      "fps": 15.0,
      "counters": {"dropped":0,"overflow":0,"duplicate":0,"reorder":0,"timeout":0,"error":0},
      "sdr_status": "ok", "fpga_status": "ok", "npu_status": "ok"
    })";

    std::string err;
    std::optional<ResultFrame> f = parse_result_frame(QByteArray(v11), &err);
    check(f.has_value(), "parse V1.1");
    check(f->contract_version == 2 && f->model_id == "m", "V1.1 version/model");
    check(f->class_names.size() == 10 && f->scores.size() == 10, "V1.1 10 classes");
    check(f->predicted_index == 7 && f->predicted_class == "16QAM", "V1.1 predicted");
    check(f->source == Source::Mock && f->frame_id == 5, "V1.1 source/frame_id");

    const char* legacy = R"({
      "schema_version": 1,
      "frame_id": 3, "timestamp_ns": 1, "source": "FILE",
      "class_id": 3, "class_name": "16QAM", "confidence": 0.8,
      "probabilities": [0.01,0.01,0.01,0.8,0.1,0.03,0.02,0.02],
      "snr_db": 15.0, "center_frequency_hz": 2400000000.0, "sample_rate_hz": 128000.0,
      "latency_us": {"sdr_capture":1,"resample_frame":1,"plddr_transfer":1,"fpga_process":1,"npu_infer":1,"end_to_end":5},
      "fps": 15.0,
      "counters": {"dropped":0,"overflow":0,"duplicate":0,"reorder":0,"timeout":0,"error":0},
      "sdr_status": "ok", "fpga_status": "ok", "npu_status": "ok"
    })";

    std::optional<ResultFrame> g = parse_result_frame(QByteArray(legacy), &err);
    check(g.has_value(), "parse legacy");
    check(g->contract_version == 1 && g->model_id.empty(), "legacy version/model empty");
    check(g->predicted_index == 3 && g->predicted_class == "16QAM", "legacy predicted");
    check(g->class_names == legacy_class_names(), "legacy normalized class names");
    check(g->scores.size() == 8, "legacy 8 scores");
    check(g->source == Source::File, "legacy source FILE");

    std::optional<ResultFrame> bad = parse_result_frame(QByteArray("{not json"), &err);
    check(!bad.has_value() && !err.empty(), "malformed JSON rejected");

    std::optional<ResultFrame> missing =
        parse_result_frame(QByteArray(R"({"frame_id":1})"), &err);
    check(!missing.has_value(), "missing version rejected");

    // to_json round-trip.
    QByteArray out = to_json(*f);
    std::string err2;
    std::optional<ResultFrame> rt = parse_result_frame(out, &err2);
    check(rt.has_value(), "round-trip parses");
    check(rt->frame_id == f->frame_id && rt->predicted_class == f->predicted_class &&
              rt->confidence == f->confidence && rt->model_id == f->model_id,
          "round-trip fields equal");

    if (g_failures == 0) {
        std::printf("test_json_result_frame: all checks passed\n");
        return 0;
    }
    std::fprintf(stderr, "test_json_result_frame: %d check(s) failed\n", g_failures);
    return 1;
}
