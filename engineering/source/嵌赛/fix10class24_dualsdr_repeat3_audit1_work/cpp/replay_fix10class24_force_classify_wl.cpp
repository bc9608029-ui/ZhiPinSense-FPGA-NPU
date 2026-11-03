// replay_fix10class24_force_classify_wl.cpp -- fix10class24-dualsdr-repeat3-audit1
// Phase B/C main (wide-linear-corrected successor to the rxresidual-audit1 force
// classifier).  Force a gate-bypassed provisional payload recovery + the VERBATIM
// production classification chain from one failed-RX dump, and export the diagnostic
// files.  Also hosts the two Phase C byte-equivalence HARD GATES:
//   * scalar  -- production apply() == apply_provisional() on a clean PASS fixture
//   * wide-linear -- production apply() (wide-linear branch) == apply_provisional()
//                    on an image-impaired fixture that enables wide-linear
//
//   replay_fix10class24_force_classify_wl --self-test --clean24-dir DIR [--source-index N]
//   replay_fix10class24_force_classify_wl --dump-dir CAP/failed_rx/IDX
//         --clean24-dir DIR --export-dir DIR
//
// iCraft-free / libiio-free / NPU-free.

#include "replay_fix10class24_force_classify_wl.hpp"

#include <cstdio>
#include <filesystem>
#include <string>

namespace {

std::string need_value(int argc, char** argv, int& i, const char* name) {
    if (i + 1 >= argc) throw std::runtime_error(std::string("missing value for ") + name);
    return argv[++i];
}

std::string basename(const std::string& p) {
    std::string s = p;
    while (s.size() > 1 && (s.back() == '/' || s.back() == '\\')) s.pop_back();
    const std::size_t pos = s.find_last_of("/\\");
    return (pos == std::string::npos) ? s : s.substr(pos + 1);
}

std::string dirname(const std::string& p) {
    std::string s = p;
    while (s.size() > 1 && (s.back() == '/' || s.back() == '\\')) s.pop_back();
    const std::size_t pos = s.find_last_of("/\\");
    return (pos == std::string::npos) ? "." : s.substr(0, pos);
}

}  // namespace

int main(int argc, char** argv) {
    try {
        std::string dump_dir, clean24_dir, export_dir;
        long long source_index = 1500;
        bool self_test = false;
        for (int i = 1; i < argc; ++i) {
            const std::string a = argv[i];
            if (a == "--self-test") self_test = true;
            else if (a == "--dump-dir") dump_dir = need_value(argc, argv, i, "--dump-dir");
            else if (a == "--clean24-dir")
                clean24_dir = need_value(argc, argv, i, "--clean24-dir");
            else if (a == "--export-dir")
                export_dir = need_value(argc, argv, i, "--export-dir");
            else if (a == "--source-index")
                source_index = std::stoll(need_value(argc, argv, i, "--source-index"));
            else throw std::runtime_error("unknown argument: " + a);
        }

        if (self_test) {
            if (clean24_dir.empty())
                throw std::runtime_error("--self-test requires --clean24-dir");

            // (1) scalar PASS-fixture equivalence (needs the D2 manifest).
            const replay24wl::EquivalenceResult e =
                replay24wl::run_pass_fixture_equivalence(clean24_dir, source_index);
            const bool scalar_ok = e.apply_identical && e.payload_iq_identical &&
                                   e.recovered_stream_identical &&
                                   e.classification_window_identical && e.model_input_identical;

            // (2) wide-linear fixture equivalence (image-impaired; no D2 needed).
            const bool wl_ok = replay24wl::run_wide_linear_fixture_equivalence();

            const bool all_ok = scalar_ok && wl_ok;
            std::printf("FIX10CLASS24_FORCE_CLASSIFY_WL_SELF_TEST "
                        "apply_identical=%d payload_iq_identical=%d recovered_stream_identical=%d "
                        "classification_window_identical=%d model_input_identical=%d "
                        "wide_linear_apply_identical=%d result=%s\n",
                        e.apply_identical ? 1 : 0, e.payload_iq_identical ? 1 : 0,
                        e.recovered_stream_identical ? 1 : 0,
                        e.classification_window_identical ? 1 : 0,
                        e.model_input_identical ? 1 : 0, wl_ok ? 1 : 0,
                        all_ok ? "PASS" : "FAIL");
            return all_ok ? 0 : 1;
        }

        if (dump_dir.empty() || clean24_dir.empty() || export_dir.empty())
            throw std::runtime_error(
                "usage: replay_fix10class24_force_classify_wl --self-test --clean24-dir DIR "
                "[--source-index N] | --dump-dir DIR --clean24-dir DIR --export-dir DIR");

        // capture_id = the round directory (dump_dir == <capture_id>/failed_rx/<idx>).
        const std::string capture_id = basename(dirname(dirname(dump_dir)));
        const std::string idx = basename(dump_dir);
        if (capture_id == "." || capture_id.empty() || idx == "." || idx.empty())
            throw std::runtime_error("cannot derive capture_id/source_index from --dump-dir");
        source_index = std::stoll(idx);

        const replay24wl::ForceClassifyResult r =
            replay24wl::force_classify_from_dir(dump_dir, clean24_dir, capture_id,
                                                source_index);

        // Idempotency guard: refuse to overwrite an existing export unless its identity
        // (raw_rx_sha256 + source_index) matches what we are about to write.
        const std::string target_dir =
            export_dir + "/" + capture_id + "/" + std::to_string(source_index);
        const std::string prior_json = target_dir + "/forced_recovery.json";
        if (std::filesystem::exists(prior_json)) {
            const std::string prior = replay24::read_file(prior_json);
            const std::string prior_sha = replay24::json_str(prior, "raw_rx_sha256");
            const long long prior_idx = replay24::json_int(prior, "source_index");
            if (prior_sha != r.raw_rx_sha256 || prior_idx != r.source_index)
                throw std::runtime_error(
                    "refusing to overwrite existing export with a DIFFERENT input identity: " +
                    target_dir);
        }

        std::filesystem::create_directories(target_dir);
        replay24wl::write_export(export_dir, r);

        const bool canonical_ok =
            r.timing_ok && r.coarse_ok && r.fine_ok && r.corr_ok && r.resid_ok;
        std::printf("FIX10CLASS24_FORCE_CLASSIFY_WL capture_id=%s source_index=%lld "
                    "source_class=%d residual=%.9f corr=%.9f canonical_crosscheck=%s "
                    "reconstruction_consistent=%d "
                    "actual_failure=%s actual_failure_enum=%d "
                    "wide_linear_enabled=%d wl_scalar_val=%.9f wl_val=%.9f "
                    "wl_image_ratio=%.9f model_input_sha=%s\n",
                    r.capture_id.c_str(), r.source_index, r.source_class,
                    r.payload_training_residual, r.payload_training_corr,
                    canonical_ok ? "PASS" : "FAIL",
                    r.reconstruction_consistent ? 1 : 0,
                    iqrfrec::failure_token(r.actual_failure),
                    static_cast<int>(r.actual_failure),
                    r.wl.enabled ? 1 : 0,
                    r.wl.scalar_validation_residual, r.wl.validation_residual,
                    r.wl.image_ratio, r.chain.cw.aligned_sha256.c_str());
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "replay_fix10class24_force_classify_wl: ERROR: %s\n", e.what());
        return 2;
    }
}
