#pragma once

// iq_clean2b_sidecar.hpp -- fix10clean2b: the radioml-compatible-clean-d2-2p56m
// sidecar loader + manifest-name selection.
//
// The clean2b payload lives in clean2b_smoke_manifest.tsv, a 27-column manifest
// whose FIRST 24 columns are byte-for-byte the route_d2_rf_manifest.tsv schema
// (sample_index ... recovered_tensor_file), plus three provenance columns:
//
//   tx_scale               == kAdcFullScale / tx_rms   (finite, >0, self-consistent)
//   frozen_raw24_pred      == raw24_class
//   frozen_deployed23_pred == deployed23_class
//
// load_clean2b_sidecar parses the first 24 columns FIELD-FOR-FIELD like
// iqdloop::load_d2_sidecar (same fail-closed SHA/size/sample-rate/class checks);
// the three extra columns are provenance cross-checks only and are NOT stored in
// iqdloop::FrozenIq (there are no fields for them).  The runner still takes the
// frozen prediction from the 6-column baseline, never from this manifest.
//
// manifest_name_for_kind / manifest_path_for_kind select the sidecar file by
// input_kind and FAIL CLOSED on any unknown kind (never a silent fallback to
// route_d2_rf_manifest.tsv).  This is the board's twin of the PC's Python
// manifest_name_for_kind in host_tools/pc_tx_sdr_fix10.py.

#include "iq_digital_loopback.hpp"

#include <cmath>
#include <cstdint>
#include <fstream>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace clean2b {

inline const char* manifest_name_for_kind(const std::string& input_kind) {
    if (input_kind == "radioml-d2-2p56m") return "route_d2_rf_manifest.tsv";
    if (input_kind == "radioml-compatible-clean-d2-2p56m")
        return "clean2b_smoke_manifest.tsv";
    throw std::runtime_error(
        "iq-clean2b: unknown --input-kind: " + input_kind +
        " (use radioml-d2-2p56m|radioml-compatible-clean-d2-2p56m)");
}

// Mirror of iqpctbrx::d2_manifest_path's join convention (trailing-sep aware),
// but parameterised by input_kind.  d2_manifest_path itself is unchanged.
inline std::string manifest_path_for_kind(const std::string& frozen_dir,
                                          const std::string& input_kind) {
    const std::string name = manifest_name_for_kind(input_kind);
    if (frozen_dir.empty()) return name;
    const char c = frozen_dir.back();
    return (c == '/' || c == '\\') ? frozen_dir + name : frozen_dir + "/" + name;
}

inline std::vector<iqdloop::FrozenIq> load_clean2b_sidecar(const std::string& dir) {
    const std::string tsv_path = dir + "/clean2b_smoke_manifest.tsv";
    std::ifstream tsv(tsv_path);
    if (!tsv)
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: missing " + tsv_path);

    std::vector<iqdloop::FrozenIq> out;
    std::set<long long> seen_source_index;
    std::string line;
    bool first = true;
    while (std::getline(tsv, line)) {
        if (line.empty()) continue;
        if (line[0] == '#') { first = false; continue; }
        if (first) { first = false; continue; }   // header row (27 columns)
        const std::vector<std::string> f = iqdloop::split_tab(line);
        if (f.size() < 27)
            throw std::runtime_error(
                "iq-clean2b: malformed clean2b_smoke_manifest.tsv row "
                "(expected 27 columns): " + line);

        iqdloop::FrozenIq q;
        // Columns 0..23 == route_d2_rf_manifest.tsv schema (see load_d2_sidecar).
        q.source_index = iqdloop::parse_ll(f[1]);
        if (!seen_source_index.insert(q.source_index).second)
            throw std::runtime_error("iq-clean2b: duplicate source_index " +
                                     std::to_string(q.source_index) +
                                     " in clean2b_smoke_manifest.tsv");
        q.source_class = static_cast<int>(iqdloop::parse_ll(f[2]));
        const int deployed23 = static_cast<int>(iqdloop::parse_ll(f[3]));
        q.modulation = f[4];
        q.snr_db = iqdloop::parse_d(f[5]);
        q.split_role = f[6];
        q.original_dc_i = iqdloop::parse_d(f[8]);
        q.original_dc_q = iqdloop::parse_d(f[9]);
        q.d2_rec_scale = iqdloop::parse_d(f[11]);
        q.complex_count = iqdloop::parse_u64(f[12]);
        q.sample_rate = iqdloop::parse_u64(f[13]);
        q.original_sha256 = f[19];           // source clean sample identity
        q.sha256 = f[20];                    // quantized_sha256 (the ci16 TX bytes)
        q.recovered_tensor_sha256 = f[21];
        q.file_name = f[22];                 // quantized_file
        q.recovered_tensor_file = f[23];     // recovered_tensor_file (8192-byte f32)
        q.is_calibration = (q.split_role == "calibration");

        // Three extra provenance columns (fail-closed, never stored).
        const double tx_rms = iqdloop::parse_d(f[14]);
        const double tx_scale = iqdloop::parse_d(f[24]);
        const int frozen_raw24_pred = static_cast<int>(iqdloop::parse_ll(f[25]));
        const int frozen_deployed23_pred = static_cast<int>(iqdloop::parse_ll(f[26]));

        if (q.split_role != "calibration" && q.split_role != "holdout")
            throw std::runtime_error("iq-clean2b: unexpected split_role '" +
                                     q.split_role + "' for " + q.file_name);
        if (q.source_class < 0 || q.source_class >= rml23::kSourceClassCount)
            throw std::runtime_error("iq-clean2b: raw24_class out of range for " +
                                     q.file_name);
        if (deployed23 < 0 || deployed23 >= rml23::kDeployedClassCount)
            throw std::runtime_error("iq-clean2b: deployed23_class out of range for " +
                                     q.file_name);
        if (deployed23 != rml23::kSourceToDeployed[q.source_class])
            throw std::runtime_error("iq-clean2b: deployed23_class (" +
                                     std::to_string(deployed23) + ") != mapping (" +
                                     std::to_string(rml23::kSourceToDeployed[q.source_class]) +
                                     ") for " + q.file_name);
        if (frozen_raw24_pred != q.source_class)
            throw std::runtime_error("iq-clean2b: frozen_raw24_pred (" +
                                     std::to_string(frozen_raw24_pred) +
                                     ") != raw24_class (" +
                                     std::to_string(q.source_class) + ") for " + q.file_name);
        if (frozen_deployed23_pred != deployed23)
            throw std::runtime_error("iq-clean2b: frozen_deployed23_pred (" +
                                     std::to_string(frozen_deployed23_pred) +
                                     ") != deployed23_class (" +
                                     std::to_string(deployed23) + ") for " + q.file_name);
        if (q.sample_rate != iqdloop::kFrozenFsIn)
            throw std::runtime_error("iq-clean2b: frozen sample rate " +
                                     std::to_string(q.sample_rate) + " != " +
                                     std::to_string(iqdloop::kFrozenFsIn) + " for " +
                                     q.file_name);

        // tx_scale provenance: finite, >0, self-consistent with tx_rms.
        if (!(tx_rms > 0.0) || !std::isfinite(tx_rms))
            throw std::runtime_error("iq-clean2b: bad tx_rms for " + q.file_name);
        if (!std::isfinite(tx_scale) || tx_scale <= 0.0)
            throw std::runtime_error("iq-clean2b: bad tx_scale for " + q.file_name);
        const double expected_scale =
            static_cast<double>(chain::kAdcFullScale) / tx_rms;
        if (std::fabs(tx_scale - expected_scale) / expected_scale > 1e-6)
            throw std::runtime_error("iq-clean2b: tx_scale " + std::to_string(tx_scale) +
                                     " != kAdcFullScale/tx_rms " +
                                     std::to_string(expected_scale) + " for " + q.file_name);

        if (q.file_name.empty() || q.file_name.find('/') != std::string::npos ||
            q.file_name.find('\\') != std::string::npos ||
            q.file_name.find("..") != std::string::npos)
            throw std::runtime_error("iq-clean2b: unsafe quantized_file in clean2b "
                                     "manifest: " + q.file_name);
        if (q.recovered_tensor_file.empty() ||
            q.recovered_tensor_file.find('/') != std::string::npos ||
            q.recovered_tensor_file.find('\\') != std::string::npos ||
            q.recovered_tensor_file.find("..") != std::string::npos)
            throw std::runtime_error("iq-clean2b: unsafe recovered_tensor_file in clean2b "
                                     "manifest: " + q.recovered_tensor_file);
        if (!iqdloop::is_hex64(q.original_sha256))
            throw std::runtime_error("iq-clean2b: original_sha256 not 64-hex for " +
                                     q.file_name);
        if (!iqdloop::is_hex64(q.sha256))
            throw std::runtime_error("iq-clean2b: quantized_sha256 not 64-hex for " +
                                     q.file_name);
        if (!iqdloop::is_hex64(q.recovered_tensor_sha256))
            throw std::runtime_error("iq-clean2b: recovered_tensor_sha256 not 64-hex "
                                     "for " + q.file_name);

        q.dtype = "ci16le";
        q.layout = "interleaved_iq";
        q.byte_count = q.complex_count * 4;
        q.seed = 0;
        q.deployed_class = deployed23;
        q.has_frozen_ref = false;
        q.has_d2_restore = true;
        q.has_recovered_ref = true;

        // SHA/size verify the ci16 (fail-closed, on the fly).
        std::uint64_t got_complex = 0;
        q.path = iqdloop::verify_frozen_file(dir, q.file_name, q.byte_count, q.sha256,
                                             &got_complex);
        if (got_complex != q.complex_count)
            throw std::runtime_error("iq-clean2b: complex count mismatch for " +
                                     q.file_name);

        // The D2 recovered tensor is the [2,1024] fp32 reference; hash it fail-closed.
        q.recovered_tensor_path = dir + "/" + q.recovered_tensor_file;
        {
            std::size_t tsz = 0;
            bool tok = false;
            const std::string got =
                iqdloop::sha256_of_file(q.recovered_tensor_path, &tsz, &tok);
            if (!tok)
                throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: cannot read " +
                                         q.recovered_tensor_path);
            if (tsz != chain::kTensorBytes)
                throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: " +
                                         q.recovered_tensor_file + " size " +
                                         std::to_string(tsz) + " != " +
                                         std::to_string(chain::kTensorBytes));
            if (got != q.recovered_tensor_sha256)
                throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: recovered "
                                         "tensor SHA mismatch for " +
                                         q.recovered_tensor_file);
        }
        out.push_back(std::move(q));
    }
    if (out.empty())
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: zero samples in " +
                                 tsv_path);
    return out;
}

}  // namespace clean2b
