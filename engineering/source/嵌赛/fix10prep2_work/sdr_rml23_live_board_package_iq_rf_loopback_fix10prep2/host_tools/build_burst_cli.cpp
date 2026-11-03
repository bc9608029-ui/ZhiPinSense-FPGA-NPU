// build_burst_cli.cpp -- fix10prep2 PC-side TX burst generator (WSL g++).
//
// Rebuilds the EXACT training-frame TX burst the board expects, from the SAME h5
// iq_rf_training_frame.hpp / iq_digital_loopback.hpp the board uses, so the PC and
// the board derive byte-identical payload_sha_pre / payload_sha_post / burst_sha /
// tx_scale from the same frozen ci16 + --rf-tx-target-rms.  Python must NOT re-
// implement the frame math (rounding / LCG / Zadoff-Chu drift are a red line).
//
// Usage:
//   build_burst_cli --ci16 <file.ci16> --complex-count 53760
//       --expect-sha <64-hex> --target-rms 2048
//       --out-burst <burst.bin> --out-json <manifest.json>
//
// The manifest is emitted with 17-significant-digit doubles (iqpctbrx::json_dump),
// which round-trip exactly through Python's float repr and back, so the PC's tx_scale
// is the bit-identical double the board recomputes independently.
//
// Exit codes: 0 = clean build; 1 = fail-closed (SHA / length / clip / I/O / args).

#include "../board_package/iq_pc_tx_board_rx_transfer_fix10.hpp"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>

namespace {

std::string get_arg(int argc, char** argv, const char* key) {
    for (int i = 1; i + 1 < argc; ++i)
        if (std::strcmp(argv[i], key) == 0) return argv[i + 1];
    return std::string();
}

void usage() {
    std::fprintf(stderr,
        "usage: build_burst_cli --ci16 <file> --complex-count <n> --expect-sha <64-hex> "
        "--target-rms <rms> --out-burst <file> --out-json <file>\n"
        "       build_burst_cli --self-check\n");
}

bool has_arg(int argc, char** argv, const char* key) {
    for (int i = 1; i < argc; ++i)
        if (std::strcmp(argv[i], key) == 0) return true;
    return false;
}

}  // namespace

int main(int argc, char** argv) {
    // Compile-once warm-up: prove the tool links against the authoritative h5 frame
    // header and report the frozen frame identity, without touching a ci16 file.
    if (has_arg(argc, argv, "--self-check")) {
        std::printf("build_burst_cli self-check ok "
                    "kPayloadComplex=%zu kTotalBurstComplex=%zu kFs=%llu "
                    "kPayloadTrainingSamplesPerSymbol=%zu kPayloadTrainingOffset=%zu\n",
                    static_cast<std::size_t>(iqrftrain::kPayloadComplex),
                    static_cast<std::size_t>(iqrftrain::kTotalBurstComplex),
                    static_cast<unsigned long long>(iqrftrain::kFs),
                    static_cast<std::size_t>(iqrftrain::kPayloadTrainingSamplesPerSymbol),
                    static_cast<std::size_t>(iqrftrain::kPayloadTrainingOffset));
        return 0;
    }

    const std::string ci16 = get_arg(argc, argv, "--ci16");
    const std::string cc_s = get_arg(argc, argv, "--complex-count");
    const std::string sha = get_arg(argc, argv, "--expect-sha");
    const std::string rms_s = get_arg(argc, argv, "--target-rms");
    const std::string out_burst = get_arg(argc, argv, "--out-burst");
    const std::string out_json = get_arg(argc, argv, "--out-json");
    if (ci16.empty() || cc_s.empty() || sha.empty() || rms_s.empty() ||
        out_burst.empty() || out_json.empty()) {
        usage();
        return 1;
    }

    const std::uint64_t cc = static_cast<std::uint64_t>(std::atoll(cc_s.c_str()));
    const double target_rms = std::atof(rms_s.c_str());
    if (cc == 0 || target_rms <= 0.0) {
        std::fprintf(stderr, "build_burst_cli: bad --complex-count / --target-rms\n");
        return 1;
    }

    iqpctbrx::TxBurstBuild r;
    try {
        r = iqpctbrx::build_tx_burst_from_frozen(ci16, cc, sha, target_rms);
    } catch (const std::exception& e) {
        std::fprintf(stderr, "build_burst_cli: build failed: %s\n", e.what());
        return 1;
    }

    // A pre- or post-scale clip means the waveform would be corrupt; the board's
    // readiness provenance check rejects it, so fail closed here too.
    if (r.clip_pre || r.clip_post) {
        std::fprintf(stderr, "build_burst_cli: clip (pre=%d post=%d)\n",
                     r.clip_pre ? 1 : 0, r.clip_post ? 1 : 0);
    }

    // Write the burst bytes (interleaved int16, little-endian).
    {
        std::ofstream bo(out_burst, std::ios::binary);
        if (!bo) { std::fprintf(stderr, "build_burst_cli: cannot write %s\n",
                                out_burst.c_str()); return 1; }
        bo.write(reinterpret_cast<const char*>(r.burst.data()),
                 static_cast<std::streamsize>(r.burst.size() * sizeof(std::int16_t)));
        if (!bo) { std::fprintf(stderr, "build_burst_cli: short write %s\n",
                                out_burst.c_str()); return 1; }
    }

    // Write the provenance manifest (exact 17-digit doubles).
    {
        using iqpctbrx::Json;
        using iqpctbrx::boolean;
        using iqpctbrx::num;
        using iqpctbrx::obj;
        using iqpctbrx::str;
        const Json m = obj({
            {"payload_sha_pre", str(r.payload_sha_pre)},
            {"payload_sha_post", str(r.payload_sha_post)},
            {"burst_sha", str(r.burst_sha)},
            {"tx_scale", num(r.tx_scale)},
            {"native_rms", num(r.native_rms)},
            {"target_rms", num(r.target_rms)},
            {"peak_pre", num(r.peak_pre)},
            {"peak_post", num(r.peak_post)},
            {"clip_pre", boolean(r.clip_pre)},
            {"clip_post", boolean(r.clip_post)},
            {"burst_complex", num(static_cast<double>(r.burst.size() / 2))},
            {"burst_bytes",
             num(static_cast<double>(r.burst.size() * sizeof(std::int16_t)))},
        });
        std::ofstream jo(out_json, std::ios::binary);
        if (!jo) { std::fprintf(stderr, "build_burst_cli: cannot write %s\n",
                                out_json.c_str()); return 1; }
        const std::string text = iqpctbrx::json_dump(m);
        jo << text;
        if (!jo) { std::fprintf(stderr, "build_burst_cli: short write %s\n",
                                out_json.c_str()); return 1; }
    }

    std::printf("build_burst_cli: ok payload_sha_pre=%s burst_sha=%s tx_scale=%.17g "
                "burst_complex=%zu\n",
                r.payload_sha_pre.c_str(), r.burst_sha.c_str(), r.tx_scale,
                r.burst.size() / 2);
    return (r.clip_pre || r.clip_post) ? 1 : 0;
}
