// test_radioml_independent_rx.cpp -- host chain test for the fix1 (+ fix1v2 board)
// independent-RX runner's FILE capture path (fix10class24 Task D, G2).
//
// What it proves (no iCraft / no libiio / no device):
//   1. rx_int16 is REALLY filled from the burst .i16 (read_i16_file + deinterleave),
//      i.e. the exact bytes the board's --capture-source=file path feeds;
//   2. those IQ samples REALLY enter recovery + classification
//      (recover_and_classify_one<MockNpu> -- the SAME function the runner calls),
//      and the recovered [2,1024] f32 model input is byte-identical to the Python
//      B-layer reference (independent_rx_replay.tsv model_input_sha256 column +
//      layers/<n>.recovered.tensor.bin), for BOTH the v1 and v2 public-protocol
//      conversions (same layout, different uniform S -> different recovered SHA).
//   3. classification runs (mock infer receives the recovered tensor, raw24_predict
//      returns a finite top-1).
//
// The device (board capture + PC-TX control channel) branch is NOT exercised here:
// it needs pluto + libiio; it is compiled (-fsyntax-only) in the board build and its
// protocol is exercised separately over 127.0.0.1 by the G4 simulated-device test.
//
// The recovered SHA is verified against the B-layer reference, NOT the manifest's
// A-layer model_input_sha256 (which is the ORIGINAL un-quantized window).  Clean
// digital recovery yields timing=0, cfo=0, a=1, b=0, residual=0, recovered =
// lround(wf*S)/S, so the two SHAs differ by construction.

#include "../board_package/radioml_independent_rx_runner.hpp"

#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <string>
#include <vector>

#include <sys/stat.h>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

// Mock NPU: proves infer() is actually called with the recovered tensor bytes by
// forwarding the first 24 real-component floats as pseudo-logits.  Deterministic and
// finite for clean-digital recovered inputs.
struct MockNpu {
    int calls = 0;
    void infer(const float* tensor, std::vector<float>& out) {
        ++calls;
        out.assign(24, 0.0f);
        for (int i = 0; i < 24; ++i) out[static_cast<std::size_t>(i)] = tensor[i];
    }
};

std::vector<std::string> split_tab(const std::string& line) {
    std::vector<std::string> f;
    std::size_t start = 0;
    while (true) {
        const std::size_t pos = line.find('\t', start);
        if (pos == std::string::npos) { f.push_back(line.substr(start)); break; }
        f.push_back(line.substr(start, pos - start));
        start = pos + 1;
    }
    return f;
}

// Reference map: source_index -> B-layer recovered model_input_sha256 (column 19,
// the LAST column of independent_rx_replay.tsv).
std::map<int, std::string> load_reference_sha(const std::string& tsv_path) {
    std::ifstream f(tsv_path);
    if (!f) throw std::runtime_error("cannot open reference tsv " + tsv_path);
    std::map<int, std::string> m;
    std::string line;
    bool first = true;
    while (std::getline(f, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;
        if (first) { first = false; continue; }   // header
        const std::vector<std::string> c = split_tab(line);
        if (c.size() < 19) throw std::runtime_error("short reference row: " + line);
        const int si = std::atoi(c[0].c_str());
        m[si] = c[18];                             // 0-based: column 19 == index 18
    }
    if (m.size() != 24) throw std::runtime_error(
        "reference tsv has " + std::to_string(m.size()) + " rows (want 24)");
    return m;
}

std::string file_sha256(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot read " + path);
    std::vector<char> buf((std::istreambuf_iterator<char>(f)),
                          std::istreambuf_iterator<char>());
    return sdr::Sha256::hex(buf.data(), buf.size());
}

void run_file_chain(const std::string& tx_dir, const std::string& ref_tsv,
                    const std::string& ref_layers, const std::string& out_dir) {
    // Fail-closed fresh out dir (same discipline as the runner).
    {
        struct stat st;
        if (::stat(out_dir.c_str(), &st) == 0)
            throw std::runtime_error("--out-dir already exists: " + out_dir);
        if (::mkdir(out_dir.c_str(), 0777) != 0)
            throw std::runtime_error("cannot create --out-dir " + out_dir + ": " +
                                     std::strerror(errno));
    }

    const std::string manifest_path =
        iqindepfix1::join_path(tx_dir, "public_protocol_tx_manifest.tsv");
    const std::vector<iqindepfix1::IndependentRxFrame> frames =
        iqindepfix1::load_independent_rx_manifest(manifest_path);
    const std::map<int, std::string> ref_sha = load_reference_sha(ref_tsv);
    check(frames.size() == 24, "manifest: 24 rows (got " +
          std::to_string(frames.size()) + ")");

    const std::string source_id = frames[0].source_id;
    const std::string version = frames[0].conversion_version;
    std::printf("  tx_dir=%s source_id=%s version=%s\n", tx_dir.c_str(),
                source_id.c_str(), version.c_str());

    MockNpu npu;
    int sha_match = 0, bin_match = 0, gated = 0, finite = 0, repeatable = 0;
    for (const auto& fr : frames) {
        // 1. REAL rx_int16 fill (file source, same path the runner uses).
        std::vector<std::int16_t> rx_int16;
        std::string perr;
        const std::string burst_path = iqindepfix1::join_path(tx_dir, fr.burst_file);
        if (!iqindepfix1::read_i16_file(burst_path, rx_int16, &perr))
            throw std::runtime_error("read_i16_file: " + perr);
        if (rx_int16.size() != 2 * iqindepfix1::kTotalBurstComplex)
            throw std::runtime_error("burst int16 count " +
                std::to_string(rx_int16.size()) + " != " +
                std::to_string(2 * iqindepfix1::kTotalBurstComplex));

        // 2. persist raw RX (R5), then deinterleave -> recovery.  The clean digital
        // burst is NOT ADC-domain: its preamble/tail/training sit at full-scale by
        // design (|v| can reach 2048), so the 12-bit clip check (kClipRail=2047) must
        // NOT be applied here -- it is scoped to device / --rx-i16 captures only.
        const std::string raw_rx_sha =
            iqindepfix1::persist_raw_rx(out_dir, fr.source_index, rx_int16);
        const std::vector<std::complex<double>> rx =
            iqrftrain::deinterleave(rx_int16);
        const auto o = iqindepfix1::recover_and_classify_one<MockNpu>(
            npu, rx, fr, fr.unscale, out_dir, /*capture_ok=*/true,
            /*no_sync=*/false, /*rx_clipped=*/false, raw_rx_sha);

        if (o.gated) ++gated;
        if (o.finite) ++finite;
        if (o.repeatable) ++repeatable;
        if (o.model_input_sha256 == ref_sha.at(fr.source_index)) ++sha_match;
        // R5: real logits + raw capture are persisted (not synthetic one-hot).
        if (o.logits1.size() != 24 || o.logits2.size() != 24 ||
            o.raw_rx_sha256.empty() || o.logits_sha256.empty())
            throw std::runtime_error("src " + std::to_string(fr.source_index) +
                " missing logits/raw-rx persistence (logits1=" +
                std::to_string(o.logits1.size()) + " logits2=" +
                std::to_string(o.logits2.size()) + ")");
        if (!std::isfinite(o.residual_rel) || o.no_sync || o.rx_clipped ||
            !o.capture_ok)
            throw std::runtime_error("src " + std::to_string(fr.source_index) +
                " bad clean-digital flags (no_sync/rx_clipped/capture_ok)");

        // 3. byte-compare the emitted recovered tensor vs the Python B-layer bin.
        const std::string got_bin = iqindepfix1::join_path(out_dir,
            std::to_string(fr.source_index) + ".recovered.tensor.bin");
        const std::string ref_bin = iqindepfix1::join_path(ref_layers,
            std::to_string(fr.source_index) + ".recovered.tensor.bin");
        if (file_sha256(got_bin) == file_sha256(ref_bin)) ++bin_match;

        std::printf("  src=%2d class=%s residual=%.3e residual_rel=%.3e gated=%d "
                    "finite=%d repeatable=%d pred=%d sha_ok=%d bin_ok=%d\n",
                    fr.source_index, fr.class_name.c_str(), o.residual,
                    o.residual_rel, o.gated ? 1 : 0, o.finite ? 1 : 0,
                    o.repeatable ? 1 : 0, o.board_pred,
                    o.model_input_sha256 == ref_sha.at(fr.source_index) ? 1 : 0,
                    file_sha256(got_bin) == file_sha256(ref_bin) ? 1 : 0);
    }

    check(sha_match == 24, "recovered model_input_sha256 == B-layer reference 24/24 "
          "(got " + std::to_string(sha_match) + ")");
    check(bin_match == 24, "recovered tensor bytes == Python B-layer bin 24/24 "
          "(got " + std::to_string(bin_match) + ")");
    check(gated == 24, "clean digital recovery gated 24/24 (got " +
          std::to_string(gated) + ")");
    check(finite == 24, "classification finite 24/24 (got " +
          std::to_string(finite) + ")");
    check(repeatable == 24, "infer-twice repeatable 24/24 (got " +
          std::to_string(repeatable) + ")");
    check(npu.calls == 48, "mock infer called 48 times (infer-twice x 24; got " +
          std::to_string(npu.calls) + ")");
    check(frames[0].model_input_sha256 != ref_sha.at(1),
          "A-layer manifest SHA != B-layer recovered SHA (recovery is real, not a copy)");
}

}  // namespace

int main(int argc, char** argv) {
    std::printf("test_radioml_independent_rx\n");

    const std::string tx_dir = [&] {
        for (int i = 1; i + 1 < argc; ++i)
            if (std::string(argv[i]) == "--tx-dir") return std::string(argv[i + 1]);
        return std::string();
    }();
    const std::string ref_tsv = [&] {
        for (int i = 1; i + 1 < argc; ++i)
            if (std::string(argv[i]) == "--reference-tsv") return std::string(argv[i + 1]);
        return std::string();
    }();
    const std::string ref_layers = [&] {
        for (int i = 1; i + 1 < argc; ++i)
            if (std::string(argv[i]) == "--reference-layers") return std::string(argv[i + 1]);
        return std::string();
    }();
    const std::string out_dir = [&] {
        for (int i = 1; i + 1 < argc; ++i)
            if (std::string(argv[i]) == "--out-dir") return std::string(argv[i + 1]);
        return std::string();
    }();

    if (tx_dir.empty() || ref_tsv.empty() || ref_layers.empty() || out_dir.empty()) {
        std::printf("usage: test_radioml_independent_rx --tx-dir <public-protocol tx dir> "
                    "--reference-tsv <independent_rx_replay.tsv> "
                    "--reference-layers <layers dir> --out-dir <fresh dir>\n");
        return 2;
    }

    try {
        run_file_chain(tx_dir, ref_tsv, ref_layers, out_dir);
    } catch (const std::exception& e) {
        std::printf("  EXCEPTION: %s\n", e.what());
        ++g_fail;
    }

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
