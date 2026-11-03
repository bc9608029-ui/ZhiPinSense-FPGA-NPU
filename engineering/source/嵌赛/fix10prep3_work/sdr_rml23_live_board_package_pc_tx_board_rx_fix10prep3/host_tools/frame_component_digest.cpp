// frame_component_digest.cpp -- fix10prep3 cross-architecture training-frame
// component digest.
//
// Goal: prove WHERE the x86 (PC/WSL) and ARM (board) training-frame bursts diverge,
// by splitting the full burst into its 6 training components (preamble / settling-zero
// / payload-training / scaled payload / guard-zero / tail) plus the full burst, writing
// each as a little-endian interleaved-int16 CI16 file, and hashing every segment + the
// 3 shared training headers.  The SAME source compiles identically on x86 (WSL g++) and
// ARM (board g++), so the two outputs can be compared segment-by-segment to locate the
// first cross-architecture difference.
//
// This tool is iCraft-free and libiio-free and touches no device: it only loads the
// frozen D2 ci16 payload, rebuilds the training-frame burst through the SAME
// iqpctbrx::build_tx_burst_from_frozen() the PC and board already use, and slices it.
// It must NOT re-implement the frame math (red line).
//
// Usage:
//   frame_component_digest --frozen-dir DIR --source-index N --target-rms RMS
//       --out-dir DIR --source-root DIR
//   frame_component_digest --self-check
//
// Exit codes: 0 = clean; 1 = fail-closed (missing/duplicate sample, SHA mismatch,
//             bad endianness, I/O, args).
//
// The 7 output files are: preamble.ci16, settling_zero.ci16, payload_training.ci16,
// scaled_payload.ci16, guard_zero.ci16, tail.ci16, full_burst.ci16, plus
// frame_components.json.  --out-dir must already exist (the wrapper / caller mkdirs).

#include "iq_pc_tx_board_rx_transfer_fix10.hpp"   // -I board_package
#include "sha256.hpp"                              // -I sdr_adapter

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <utility>
#include <vector>

namespace {

std::string get_arg(int argc, char** argv, const char* key) {
    for (int i = 1; i + 1 < argc; ++i)
        if (std::strcmp(argv[i], key) == 0) return argv[i + 1];
    return std::string();
}

bool has_arg(int argc, char** argv, const char* key) {
    for (int i = 1; i < argc; ++i)
        if (std::strcmp(argv[i], key) == 0) return true;
    return false;
}

void usage() {
    std::fprintf(stderr,
        "usage: frame_component_digest --frozen-dir DIR --source-index N "
        "--target-rms RMS --out-dir DIR --source-root DIR\n"
        "       frame_component_digest --self-check\n");
}

const char* source_arch() {
#if defined(__aarch64__)
    return "aarch64";
#elif defined(__arm__)
    return "arm32";
#elif defined(__x86_64__)
    return "x86_64";
#elif defined(__i386__)
    return "x86_32";
#else
    return "unknown";
#endif
}

// One burst segment: name, [start,end) in complex samples, output basename.
struct Segment {
    const char* name;
    std::size_t start;
    std::size_t end;
    const char* file;
};

// Write a burst slice [start,end) (complex) as interleaved int16 LE and hash it.
bool write_segment(const std::vector<std::int16_t>& burst,
                   std::size_t start, std::size_t end,
                   const std::string& path, std::string* sha_out) {
    const std::size_t n_int16 = (end - start) * 2;
    std::ofstream f(path, std::ios::binary);
    if (!f) return false;
    f.write(reinterpret_cast<const char*>(burst.data() + start * 2),
            static_cast<std::streamsize>(n_int16 * sizeof(std::int16_t)));
    if (!f) return false;
    f.close();
    bool ok = false;
    *sha_out = sdr::sha256_hex_file(path, &ok);
    return ok;
}

// Find the single manifest row for `source_index` (missing/duplicate fail-closed).
// Columns: 0 sample_index, 1 source_index, 4 modulation, 12 complex_count,
//          20 quantized_sha256, 22 quantized_file.
bool find_manifest_row(const std::string& frozen_dir, std::int64_t source_index,
                       std::string* file_name, std::uint64_t* complex_count,
                       std::string* quantized_sha, std::string* modulation) {
    const std::string tsv_path = frozen_dir + "/route_d2_rf_manifest.tsv";
    std::ifstream tsv(tsv_path);
    if (!tsv) {
        std::fprintf(stderr, "frame_component_digest: cannot read %s\n", tsv_path.c_str());
        return false;
    }
    std::string line;
    bool first = true;
    int matches = 0;
    while (std::getline(tsv, line)) {
        if (line.empty()) continue;
        if (first) { first = false; continue; }   // header row (24 columns)
        const std::vector<std::string> f = iqdloop::split_tab(line);
        if (f.size() < 24) {
            std::fprintf(stderr, "frame_component_digest: malformed manifest row (%zu cols)\n",
                         f.size());
            return false;
        }
        if (iqdloop::parse_ll(f[1]) != source_index) continue;
        ++matches;
        *file_name = f[22];
        *complex_count = iqdloop::parse_u64(f[12]);
        *quantized_sha = f[20];
        *modulation = f[4];
    }
    if (matches == 0) {
        std::fprintf(stderr, "frame_component_digest: source_index %lld not found\n",
                     static_cast<long long>(source_index));
        return false;
    }
    if (matches > 1) {
        std::fprintf(stderr, "frame_component_digest: duplicate source_index %lld\n",
                     static_cast<long long>(source_index));
        return false;
    }
    if (!iqdloop::is_hex64(*quantized_sha)) {
        std::fprintf(stderr, "frame_component_digest: quantized_sha256 not 64-hex\n");
        return false;
    }
    return true;
}

}  // namespace

int main(int argc, char** argv) {
    if (has_arg(argc, argv, "--self-check")) {
        std::printf("frame_component_digest self-check ok arch=%s "
                    "kPayloadComplex=%zu kTotalBurstComplex=%zu kFs=%llu "
                    "kPreambleComplex=%zu kPayloadTrainingOffset=%zu "
                    "kPayloadTrainingComplex=%zu kGuardComplex=%zu kTailComplex=%zu\n",
                    source_arch(),
                    static_cast<std::size_t>(iqrftrain::kPayloadComplex),
                    static_cast<std::size_t>(iqrftrain::kTotalBurstComplex),
                    static_cast<unsigned long long>(iqrftrain::kFs),
                    static_cast<std::size_t>(iqrftrain::kPreambleComplex),
                    static_cast<std::size_t>(iqrftrain::kPayloadTrainingOffset),
                    static_cast<std::size_t>(iqrftrain::kPayloadTrainingComplex),
                    static_cast<std::size_t>(iqrftrain::kGuardComplex),
                    static_cast<std::size_t>(iqrftrain::kTailComplex));
        return 0;
    }

    const std::string frozen_dir = get_arg(argc, argv, "--frozen-dir");
    const std::string si_s = get_arg(argc, argv, "--source-index");
    const std::string rms_s = get_arg(argc, argv, "--target-rms");
    const std::string out_dir = get_arg(argc, argv, "--out-dir");
    const std::string source_root = get_arg(argc, argv, "--source-root");
    if (frozen_dir.empty() || si_s.empty() || rms_s.empty() ||
        out_dir.empty() || source_root.empty()) {
        usage();
        return 1;
    }

    // Endianness / width guard: the CI16 files MUST be little-endian 16-bit.
    static_assert(sizeof(std::int16_t) == 2, "int16_t must be 2 bytes");
    const std::uint16_t endian_probe = 0x0102u;
    const bool little_endian =
        (*reinterpret_cast<const std::uint8_t*>(&endian_probe) == 0x02u);
    if (!little_endian) {
        std::fprintf(stderr, "frame_component_digest: big-endian host unsupported\n");
        return 1;
    }

    const std::int64_t source_index = static_cast<std::int64_t>(std::atoll(si_s.c_str()));
    const double target_rms = std::atof(rms_s.c_str());
    if (source_index < 0 || target_rms <= 0.0) {
        std::fprintf(stderr, "frame_component_digest: bad --source-index / --target-rms\n");
        return 1;
    }

    // Resolve the sample row from the frozen D2 manifest (fail-closed).
    std::string file_name, modulation, quantized_sha;
    std::uint64_t complex_count = 0;
    if (!find_manifest_row(frozen_dir, source_index, &file_name, &complex_count,
                           &quantized_sha, &modulation))
        return 1;

    // Hash the 3 shared training headers from --source-root (independent of -I), so the
    // two architectures record the actual source-tree headers they compiled against.
    const char* hdr_rel[3] = {
        "board_package/iq_rf_training_frame.hpp",
        "board_package/iq_digital_loopback.hpp",
        "board_package/iq_pc_tx_board_rx_transfer_fix10.hpp"};
    std::string hdr_sha[3];
    for (int i = 0; i < 3; ++i) {
        const std::string p = source_root + "/" + hdr_rel[i];
        bool ok = false;
        hdr_sha[i] = sdr::sha256_hex_file(p, &ok);
        if (!ok) {
            std::fprintf(stderr, "frame_component_digest: cannot read %s\n", p.c_str());
            return 1;
        }
    }

    // Rebuild the training-frame burst through the authoritative builder (red line: no
    // frame math re-implemented here).
    const std::string ci16_path = frozen_dir + "/" + file_name;
    iqpctbrx::TxBurstBuild r;
    try {
        r = iqpctbrx::build_tx_burst_from_frozen(ci16_path, complex_count, quantized_sha,
                                                 target_rms);
    } catch (const std::exception& e) {
        std::fprintf(stderr, "frame_component_digest: build failed: %s\n", e.what());
        return 1;
    }
    if (r.burst.size() != iqrftrain::kTotalBurstComplex * 2) {
        std::fprintf(stderr, "frame_component_digest: burst length mismatch\n");
        return 1;
    }

    // Segment definitions (complex-sample ranges, from the frozen frame constants).
    const std::size_t preamble_complex = iqrftrain::kPreambleComplex;                    // 1024
    const std::size_t training_start = iqrftrain::kPayloadTrainingOffset;                // 2048
    const std::size_t payload_start = iqrftrain::kPayloadStart;                          // 3072
    const std::size_t guard_start = iqrftrain::kPayloadStart + iqrftrain::kPayloadComplex; // 56832
    const std::size_t tail_start = iqrftrain::kTailStart;                                // 58880
    const std::size_t total = iqrftrain::kTotalBurstComplex;                             // 59904

    const Segment segs[7] = {
        {"preamble", 0, preamble_complex, "preamble.ci16"},
        {"settling_zero", preamble_complex, training_start, "settling_zero.ci16"},
        {"payload_training", training_start, payload_start, "payload_training.ci16"},
        {"scaled_payload", payload_start, guard_start, "scaled_payload.ci16"},
        {"guard_zero", guard_start, tail_start, "guard_zero.ci16"},
        {"tail", tail_start, total, "tail.ci16"},
        {"full_burst", 0, total, "full_burst.ci16"},
    };

    // Write + hash each segment.
    std::string seg_sha[7];
    for (int i = 0; i < 7; ++i) {
        const std::string path = out_dir + "/" + segs[i].file;
        if (!write_segment(r.burst, segs[i].start, segs[i].end, path, &seg_sha[i])) {
            std::fprintf(stderr, "frame_component_digest: cannot write %s\n", path.c_str());
            return 1;
        }
        std::printf("%s complex=%zu bytes=%zu sha256=%s first_difference_supported=1\n",
                    segs[i].name, segs[i].end - segs[i].start,
                    (segs[i].end - segs[i].start) * 2 * sizeof(std::int16_t),
                    seg_sha[i].c_str());
    }

    // Internal consistency: scaled_payload slice == payload_sha_post; full_burst ==
    // burst_sha.  These catch any slicing bug immediately.
    if (seg_sha[3] != r.payload_sha_post) {
        std::fprintf(stderr, "frame_component_digest: scaled_payload SHA != payload_sha_post\n");
        return 1;
    }
    if (seg_sha[6] != r.burst_sha) {
        std::fprintf(stderr, "frame_component_digest: full_burst SHA != burst_sha\n");
        return 1;
    }

    // Write frame_components.json (compact, exact 17-digit doubles via json_dump).
    using iqpctbrx::Json;
    using iqpctbrx::num;
    using iqpctbrx::obj;
    using iqpctbrx::str;

    std::vector<std::pair<std::string, Json>> seg_entries;
    seg_entries.reserve(7);
    for (int i = 0; i < 7; ++i) {
        const std::size_t complex = segs[i].end - segs[i].start;
        seg_entries.emplace_back(std::string(segs[i].name), obj({
            {"complex", num(static_cast<double>(complex))},
            {"bytes", num(static_cast<double>(complex * 2 * sizeof(std::int16_t)))},
            {"sha256", str(seg_sha[i])},
        }));
    }
    const Json segments_json = obj(std::move(seg_entries));

    const Json doc = obj({
        {"source_arch", str(source_arch())},
        {"endianness", str("little")},
        {"sizeof_int16_t", num(static_cast<double>(sizeof(std::int16_t)))},
        {"source_index", num(static_cast<double>(source_index))},
        {"file_name", str(file_name)},
        {"modulation", str(modulation)},
        {"complex_count", num(static_cast<double>(complex_count))},
        {"target_rms", num(target_rms)},
        {"tx_scale", num(r.tx_scale)},
        {"payload_sha_pre", str(r.payload_sha_pre)},
        {"payload_sha_post", str(r.payload_sha_post)},
        {"full_burst_sha", str(r.burst_sha)},
        {"segments", segments_json},
        {"header_sha256", obj({
            {"iq_rf_training_frame.hpp", str(hdr_sha[0])},
            {"iq_digital_loopback.hpp", str(hdr_sha[1])},
            {"iq_pc_tx_board_rx_transfer_fix10.hpp", str(hdr_sha[2])},
        })},
    });

    {
        std::ofstream jo(out_dir + "/frame_components.json", std::ios::binary);
        if (!jo) {
            std::fprintf(stderr, "frame_component_digest: cannot write %s/frame_components.json\n",
                         out_dir.c_str());
            return 1;
        }
        jo << iqpctbrx::json_dump(doc);
        if (!jo) {
            std::fprintf(stderr, "frame_component_digest: short write frame_components.json\n");
            return 1;
        }
    }

    std::printf("frame_component_digest: ok source_index=%lld file=%s payload_sha_pre=%s "
                "payload_sha_post=%s tx_scale=%.17g full_burst_sha=%s\n",
                static_cast<long long>(source_index), file_name.c_str(),
                r.payload_sha_pre.c_str(), r.payload_sha_post.c_str(), r.tx_scale,
                r.burst_sha.c_str());
    return 0;
}
