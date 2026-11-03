// pluto_external_tx.cpp -- Route G fix10 PC-side (WSL x86-64) external TX tool.
//
// Transmits the Route D2 AC-only payloads out a PC-attached ADALM-Pluto as the
// fix10 air-interface frame (iq_external_rf_frame.hpp), so a SEPARATE board-attached
// Pluto can receive them over a 50-ohm coax.  Two independent Plutos -> the receiver
// faces real CFO/SRO/frame-start/phase, which the board runner compensates.
//
// RF safety (see pluto_external_tx.hpp for the full sequence):
//   * --uri is REQUIRED (never auto-select); --serial is REQUIRED and matched
//     VERBATIM against dev.serial() -- a mismatch or empty read-back aborts.
//   * --atten defaults to -80 dB and is hard-capped at -40 dB (never raised).
//   * loopback is forced to 0 (digital loopback OFF) and read back == 0.
//   * on exit / SIGINT / exception / device disconnect the cyclic TX is stopped
//     (buffer destroyed) and the exit path asserts tx_running() == false.
//   * no antenna, no amplifier: 50-ohm coax only (documented, operator-supplied).
//
// Build (WSL): tools/build_external_pluto_tx.sh
// Run        : tools/run_external_pluto_tx.sh (see also Task H commands).

#include "../board_package/iq_external_rf_frame.hpp"
#include "../board_package/pluto_external_tx.hpp"
#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <unistd.h>   // usleep
#endif

namespace {

volatile std::sig_atomic_t g_stop = 0;
void on_signal(int) { g_stop = 1; }

std::string get_opt(int argc, char** argv, const char* name,
                    const std::string& def) {
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        const std::string key = name;
        if (a == key) return (i + 1 < argc) ? std::string(argv[i + 1]) : def;
        if (a.rfind(key + "=", 0) == 0) return a.substr(key.size() + 1);
    }
    return def;
}

long long opt_ll(int argc, char** argv, const char* name, long long def) {
    const std::string s = get_opt(argc, argv, name, "");
    if (s.empty()) return def;
    return std::atoll(s.c_str());
}

double opt_d(int argc, char** argv, const char* name, double def) {
    const std::string s = get_opt(argc, argv, name, "");
    if (s.empty()) return def;
    return std::atof(s.c_str());
}

std::vector<std::string> split_tab(const std::string& s) {
    std::vector<std::string> out;
    std::size_t start = 0;
    while (start <= s.size()) {
        const std::size_t pos = s.find('\t', start);
        const std::string tok = s.substr(
            start, pos == std::string::npos ? std::string::npos : pos - start);
        out.push_back(tok);
        if (pos == std::string::npos) break;
        start = pos + 1;
    }
    return out;
}

std::vector<long long> split_comma_ll(const std::string& s) {
    std::vector<long long> out;
    std::size_t start = 0;
    while (start <= s.size()) {
        const std::size_t pos = s.find(',', start);
        const std::string tok = s.substr(
            start, pos == std::string::npos ? std::string::npos : pos - start);
        if (!tok.empty()) out.push_back(std::atoll(tok.c_str()));
        if (pos == std::string::npos) break;
        start = pos + 1;
    }
    return out;
}

// One D2 manifest row (the subset the TX tool needs).
struct ManifestRow {
    long long sample_index = 0;
    std::uint64_t complex_count = 0;
    std::string sha256;
    std::string file;
};

// Read the 24-column route_d2_rf_manifest.tsv (header row + one row per sample).
// Columns: 0 sample_index, 12 complex_count, 20 quantized_sha256, 22 quantized_file.
std::vector<ManifestRow> load_manifest(const std::string& path) {
    std::ifstream tsv(path);
    if (!tsv)
        throw std::runtime_error("pluto-external-tx: cannot open manifest " + path);
    std::vector<ManifestRow> out;
    std::string line;
    bool first = true;
    while (std::getline(tsv, line)) {
        if (line.empty()) continue;
        if (line[0] == '#') { first = false; continue; }
        if (first) { first = false; continue; }   // header row
        const std::vector<std::string> f = split_tab(line);
        if (f.size() < 24)
            throw std::runtime_error(
                "pluto-external-tx: malformed manifest row (want 24 columns): " + line);
        ManifestRow r;
        r.sample_index = std::atoll(f[0].c_str());
        r.complex_count = static_cast<std::uint64_t>(std::atoll(f[12].c_str()));
        r.sha256 = f[20];
        r.file = f[22];
        if (r.complex_count != extrf::frame::kPayloadComplex)
            throw std::runtime_error(
                "pluto-external-tx: manifest complex_count " +
                std::to_string(r.complex_count) + " != frame payload " +
                std::to_string(extrf::frame::kPayloadComplex) + " for " + r.file);
        if (r.file.empty() || r.file.find('/') != std::string::npos ||
            r.file.find('\\') != std::string::npos || r.file.find("..") != std::string::npos)
            throw std::runtime_error("pluto-external-tx: unsafe quantized_file '" +
                                     r.file + "'");
        out.push_back(r);
    }
    if (out.empty())
        throw std::runtime_error("pluto-external-tx: manifest has zero rows");
    return out;
}

std::vector<std::int16_t> load_ci16(const std::string& path,
                                    std::uint64_t complex_count) {
    const std::size_t n = static_cast<std::size_t>(complex_count) * 2;
    std::vector<std::int16_t> iq(n);
    std::ifstream f(path, std::ios::binary);
    if (!f)
        throw std::runtime_error("pluto-external-tx: cannot read payload " + path);
    f.read(reinterpret_cast<char*>(iq.data()),
           static_cast<std::streamsize>(n * sizeof(std::int16_t)));
    if (static_cast<std::uint64_t>(f.gcount()) !=
        static_cast<std::uint64_t>(n * sizeof(std::int16_t)))
        throw std::runtime_error("pluto-external-tx: short read payload " + path);
    return iq;
}

}  // namespace

int main(int argc, char** argv) {
    std::signal(SIGINT, on_signal);
    std::signal(SIGTERM, on_signal);

    const std::string uri = get_opt(argc, argv, "--uri", "");
    const std::string serial = get_opt(argc, argv, "--serial", "");
    const double atten = opt_d(argc, argv, "--atten", extrf_tx::kDefaultAttenDb);
    const std::uint64_t center =
        static_cast<std::uint64_t>(opt_ll(argc, argv, "--center", 2400000000LL));
    const std::string payload_dir = get_opt(argc, argv, "--payload-dir", "");
    const std::string manifest = get_opt(argc, argv, "--manifest", "");
    const std::string index_str = get_opt(argc, argv, "--index", "");
    const long long count = opt_ll(argc, argv, "--count", 0);   // 0 = all
    const long long pause_ms = opt_ll(argc, argv, "--pause-ms", 100);
    const bool loop = (get_opt(argc, argv, "--loop", "") == "1");

    // --uri / --serial are REQUIRED and never auto-selected (RF safety, S1.2).
    if (uri.empty()) {
        std::fprintf(stderr, "pluto-external-tx: --uri is required (explicit, never "
                             "auto-select)\n");
        return 1;
    }
    if (serial.empty()) {
        std::fprintf(stderr, "pluto-external-tx: --serial is required (matched "
                             "verbatim against dev.serial())\n");
        return 1;
    }
    if (payload_dir.empty() || manifest.empty()) {
        std::fprintf(stderr, "pluto-external-tx: --payload-dir and --manifest are "
                             "required\n");
        return 1;
    }

    std::vector<ManifestRow> rows;
    try {
        rows = load_manifest(manifest);
        if (!index_str.empty()) {
            std::vector<ManifestRow> sel;
            for (long long i : split_comma_ll(index_str))
                if (i >= 0 && static_cast<std::size_t>(i) < rows.size())
                    sel.push_back(rows[static_cast<std::size_t>(i)]);
            rows = std::move(sel);
        }
        if (count > 0 && static_cast<std::size_t>(count) < rows.size())
            rows.resize(static_cast<std::size_t>(count));
        if (rows.empty())
            throw std::runtime_error("no payload rows selected");
    } catch (const std::exception& e) {
        std::fprintf(stderr, "pluto-external-tx: %s\n", e.what());
        return 1;
    }

    std::fprintf(stdout,
                 "PLUTO_EXTERNAL_TX uri=%s serial_expected=%s atten=%.3f "
                 "center=%llu payload_dir=%s manifest=%s rows=%zu pause_ms=%lld "
                 "loop=%d antenna=none coax=direct-cable ensm=not_managed_by_this_code\n",
                 uri.c_str(), serial.c_str(), atten,
                 static_cast<unsigned long long>(center), payload_dir.c_str(),
                 manifest.c_str(), rows.size(), pause_ms, loop ? 1 : 0);
    std::fflush(stdout);

    // Device open (the libiio backend opens in make_device -> a not-found is here).
    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        std::fprintf(stderr, "pluto-external-tx: device_not_found: %s\n", e.what());
        return 2;
    }

    std::size_t cursor = 0;
    const auto next_frame = [&](std::vector<std::int16_t>& frame,
                                extrf::frame::HeaderFields& fields) -> bool {
        if (g_stop) return false;
        if (cursor >= rows.size()) {
            if (!loop) return false;
            cursor = 0;
        }
        const ManifestRow& row = rows[cursor];

        const std::string path = payload_dir + "/" + row.file;
        // Verify the frozen payload SHA (fail-closed) BEFORE emitting.
        bool ok = false;
        const std::string got = sdr::sha256_hex_file(path, &ok);
        if (!ok || got != row.sha256)
            throw std::runtime_error("pluto-external-tx: payload SHA mismatch for " +
                                     row.file + " (got " + got + ", want " +
                                     row.sha256 + ")");
        const std::vector<std::int16_t> payload =
            load_ci16(path, row.complex_count);

        fields.valid = true;
        fields.version = extrf::frame::kFrameVersion;
        fields.run_id = 0;
        fields.index = static_cast<std::uint16_t>(row.sample_index);
        fields.payload_count = static_cast<std::uint16_t>(row.complex_count);
        fields.sha_short = extrf::frame::sha_short_from_hex(row.sha256);
        fields.crc16 = 0;
        fields.crc_ok = false;
        extrf::frame::attach_header_crc(fields);   // valid CRC over the first 88 bits

        frame = extrf::frame::build_frame(payload, fields);
        ++cursor;

        if (pause_ms > 0) {
            // Slice the pause so SIGINT is noticed promptly (worst-case one slice).
            long long left = pause_ms;
            while (left > 0 && !g_stop) {
                const long long slice = left < 10 ? left : 10;
#if defined(__unix__) || defined(__APPLE__)
                usleep(static_cast<useconds_t>(slice * 1000));
#else
                (void)slice;
#endif
                left -= slice;
            }
        }
        return true;
    };

    try {
        const extrf_tx::TxRunReport rep =
            extrf_tx::run_external_tx(*dev, serial, atten, center, next_frame);
        std::fprintf(stdout,
                     "PLUTO_EXTERNAL_TX_DONE frames_tx=%llu dma_mismatch=%llu "
                     "sample_rate_ok=%d atten_ok=%d loopback_ok=%d restore_ok=%d "
                     "stopped_clean=%d tx_running_after_exit=%d serial_readback=%s\n",
                     static_cast<unsigned long long>(rep.frames_tx),
                     static_cast<unsigned long long>(rep.frames_dma_mismatch),
                     rep.sample_rate_ok ? 1 : 0, rep.atten_ok ? 1 : 0,
                     rep.loopback_ok ? 1 : 0, rep.restore_ok ? 1 : 0,
                     rep.stopped_clean ? 1 : 0,
                     rep.tx_running_after_exit ? 1 : 0,
                     rep.serial_readback.c_str());
        std::fflush(stdout);
        return rep.tx_running_after_exit ? 1 : 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "pluto-external-tx: %s\n", e.what());
        return 1;
    }
}
