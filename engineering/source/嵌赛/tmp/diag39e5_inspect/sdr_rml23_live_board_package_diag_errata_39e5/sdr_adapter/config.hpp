#pragma once

// System-layer configuration (non-model) with a minimal flat key=value parser.
//
// Format (see ../config/sdr_adapter_config.conf):
//   `key = value` lines, `#` comments, blank lines ignored.
// Values are unsigned integers (base 10), doubles, booleans (true/false/1/0),
// or bare strings.  Unknown keys THROW (guards against typos); SDR fields are
// carried explicitly and set to 0 / "" = "unspecified until the device arrives".
//
// iCraft-free and header-only; unit-tested (parse round-trip, type coercion,
// unknown-key rejection).

#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>
#include <sstream>

namespace cfg {

struct Config {
    // ---- frozen model-end contract (do NOT change; see contracts/) ----
    std::uint64_t target_sample_rate = 128000;   // model-end Hz
    std::uint64_t symbol_rate = 16000;           // Hz
    std::uint64_t frame_length = 1024;           // complex samples per frame
    double adc_lsb = 1.0 / 32768.0;              // 0.000030517578125
    double receiver_scale = 1.0;                 // global frozen scalar s_adc

    // ---- SDR (TBD until device arrives; MUST NOT be guessed) ----
    std::uint64_t sdr_raw_sample_rate = 0;       // 0 = unspecified
    std::string sdr_device_type = "";            // "" = unspecified
    std::string sdr_interface = "";              // "" = unspecified (usb2/gige/...)

    // ---- ADALM-Pluto (libiio) runtime config (known device) ----
    // Device identity is known (ADALM-Pluto / AD9363); the VALUES below are
    // runtime choices, NOT fabricated measurements -- 0 / "" = unspecified and
    // must be set from board config / CLI before a real run.
    std::string pluto_uri = "";                 // e.g. "ip:192.168.2.1" / "usb:"
    std::uint64_t pluto_center_freq_hz = 0;
    std::uint64_t pluto_sample_rate_hz = 0;
    std::uint64_t pluto_rf_bandwidth_hz = 0;
    std::string pluto_gain_mode = "";           // "manual"/"slow_attack"/...; "" = unspecified
    double pluto_gain_db = 0.0;
    std::uint64_t pluto_buffer_length = 0;      // libiio buffer length; 0 = device default
    std::uint64_t pluto_timeout_ms = 0;         // per-read timeout; 0 = adapter default

    // ---- buffer sizing (0 = auto) ----
    std::uint64_t capture_buffer_frames = 0;
    std::uint64_t fpga_buffer_frames = 0;
    std::uint64_t result_buffer_frames = 0;

    // ---- timeouts (ms) ----
    std::uint64_t fpga_timeout_ms = 10000;
    std::uint64_t npu_ready_timeout_ms = 10000;

    // ---- recovery policy (see sdr_adapter/pipeline.hpp) ----
    bool abort_on_fpga_failure = true;
    bool abort_on_version_mismatch = true;
    bool continue_on_npu_timeout = false;

    // ---- logging / UI ----
    std::string log_level = "info";
    std::string log_file = "";
    bool ui_json_lines = true;
};

inline std::string trim(const std::string& s) {
    std::size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    std::size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

inline void apply_override(Config& c, const std::string& key,
                           const std::string& value) {
    const std::string v = trim(value);
    const auto u = [&](std::uint64_t& out) {
        std::size_t p = 0;
        const unsigned long long x = std::stoull(v, &p, 10);
        if (p != v.size()) throw std::runtime_error("config: invalid uint for '" + key + "'");
        out = static_cast<std::uint64_t>(x);
    };
    const auto d = [&](double& out) {
        std::size_t p = 0;
        const double x = std::stod(v, &p);
        if (p != v.size()) throw std::runtime_error("config: invalid number for '" + key + "'");
        out = x;
    };
    const auto b = [&](bool& out) {
        if (v == "true" || v == "1" || v == "yes" || v == "on") out = true;
        else if (v == "false" || v == "0" || v == "no" || v == "off") out = false;
        else throw std::runtime_error("config: invalid bool for '" + key + "'");
    };
    const auto s = [&](std::string& out) { out = v; };

    if (key == "target_sample_rate") u(c.target_sample_rate);
    else if (key == "symbol_rate") u(c.symbol_rate);
    else if (key == "frame_length") u(c.frame_length);
    else if (key == "adc_lsb") d(c.adc_lsb);
    else if (key == "receiver_scale") d(c.receiver_scale);
    else if (key == "sdr_raw_sample_rate") u(c.sdr_raw_sample_rate);
    else if (key == "sdr_device_type") s(c.sdr_device_type);
    else if (key == "sdr_interface") s(c.sdr_interface);
    else if (key == "pluto_uri") s(c.pluto_uri);
    else if (key == "pluto_center_freq_hz") u(c.pluto_center_freq_hz);
    else if (key == "pluto_sample_rate_hz") u(c.pluto_sample_rate_hz);
    else if (key == "pluto_rf_bandwidth_hz") u(c.pluto_rf_bandwidth_hz);
    else if (key == "pluto_gain_mode") s(c.pluto_gain_mode);
    else if (key == "pluto_gain_db") d(c.pluto_gain_db);
    else if (key == "pluto_buffer_length") u(c.pluto_buffer_length);
    else if (key == "pluto_timeout_ms") u(c.pluto_timeout_ms);
    else if (key == "capture_buffer_frames") u(c.capture_buffer_frames);
    else if (key == "fpga_buffer_frames") u(c.fpga_buffer_frames);
    else if (key == "result_buffer_frames") u(c.result_buffer_frames);
    else if (key == "fpga_timeout_ms") u(c.fpga_timeout_ms);
    else if (key == "npu_ready_timeout_ms") u(c.npu_ready_timeout_ms);
    else if (key == "abort_on_fpga_failure") b(c.abort_on_fpga_failure);
    else if (key == "abort_on_version_mismatch") b(c.abort_on_version_mismatch);
    else if (key == "continue_on_npu_timeout") b(c.continue_on_npu_timeout);
    else if (key == "ui_json_lines") b(c.ui_json_lines);
    else if (key == "log_level") s(c.log_level);
    else if (key == "log_file") s(c.log_file);
    else throw std::runtime_error("config: unknown key '" + key + "'");
}

inline Config parse_config_file(const std::string& path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("config: cannot open " + path);
    Config c;
    std::string line;
    std::size_t n = 0;
    while (std::getline(in, line)) {
        ++n;
        const std::string t = trim(line);
        if (t.empty() || t[0] == '#') continue;
        const std::size_t eq = t.find('=');
        if (eq == std::string::npos) {
            throw std::runtime_error("config: line " + std::to_string(n) +
                                     " has no '='");
        }
        apply_override(c, trim(t.substr(0, eq)), t.substr(eq + 1));
    }
    return c;
}

inline std::string write_default_config() {
    std::ostringstream o;
    o << "# sdr_adapter system config (non-model).\n"
      << "# SDR fields are TBD until the device arrives; 0 / empty = unspecified.\n"
      << "\n"
      << "# ---- frozen model-end contract (do not change) ----\n"
      << "target_sample_rate = 128000\n"
      << "symbol_rate = 16000\n"
      << "frame_length = 1024\n"
      << "adc_lsb = 0.000030517578125\n"
      << "receiver_scale = 1.0\n"
      << "\n"
      << "# ---- SDR (TBD) ----\n"
      << "sdr_raw_sample_rate = 0\n"
      << "sdr_device_type = \n"
      << "sdr_interface = \n"
      << "\n"
      << "# ---- ADALM-Pluto (libiio) runtime config: 0 / empty = unspecified ----\n"
      << "pluto_uri = \n"
      << "pluto_center_freq_hz = 0\n"
      << "pluto_sample_rate_hz = 0\n"
      << "pluto_rf_bandwidth_hz = 0\n"
      << "pluto_gain_mode = \n"
      << "pluto_gain_db = 0.0\n"
      << "pluto_buffer_length = 0\n"
      << "pluto_timeout_ms = 0\n"
      << "\n"
      << "# ---- buffers (0 = auto) ----\n"
      << "capture_buffer_frames = 0\n"
      << "fpga_buffer_frames = 0\n"
      << "result_buffer_frames = 0\n"
      << "\n"
      << "# ---- timeouts (ms) ----\n"
      << "fpga_timeout_ms = 10000\n"
      << "npu_ready_timeout_ms = 10000\n"
      << "\n"
      << "# ---- recovery ----\n"
      << "abort_on_fpga_failure = true\n"
      << "abort_on_version_mismatch = true\n"
      << "continue_on_npu_timeout = false\n"
      << "\n"
      << "# ---- logging / UI ----\n"
      << "log_level = info\n"
      << "log_file = \n"
      << "ui_json_lines = true\n";
    return o.str();
}

}  // namespace cfg
