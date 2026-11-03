// replay_fix10class24_failed_rx_force_classify.cpp -- fix10class24-rxresidual-audit1
// Phase B/C main: force a gate-bypassed provisional recovery + verbatim classification
// chain from one failed-RX dump, and export the 5 diagnostic files.  Also hosts the
// Phase C PASS-fixture byte-equivalence HARD GATE (--self-test).
//
//   replay_fix10class24_failed_rx_force_classify --self-test --clean24-dir DIR [--source-index N]
//   replay_fix10class24_failed_rx_force_classify --dump-dir CAP/failed_rx/IDX
//         --clean24-dir DIR --export-dir DIR
//
// iCraft-free / libiio-free / NPU-free.

#include "replay_fix10class24_failed_rx_force_classify.hpp"

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
        bool wide_linear_self_test = false;
        bool decompose = false;
        for (int i = 1; i < argc; ++i) {
            const std::string a = argv[i];
            if (a == "--self-test") self_test = true;
            else if (a == "--wide-linear-self-test") wide_linear_self_test = true;
            else if (a == "--decompose") decompose = true;
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
            const replay24force::EquivalenceResult e =
                replay24force::run_pass_fixture_equivalence(clean24_dir, source_index);
            const bool all_ok = e.apply_identical && e.payload_iq_identical &&
                                e.recovered_stream_identical &&
                                e.classification_window_identical && e.model_input_identical;
            std::printf("FIX10CLASS24_FORCE_CLASSIFY_SELF_TEST apply_identical=%d "
                        "payload_iq_identical=%d recovered_stream_identical=%d "
                        "classification_window_identical=%d model_input_identical=%d "
                        "payload_sha=%s payload_iq_sha=%s stream_sha=%s window_sha=%s "
                        "model_input_sha=%s result=%s\n",
                        e.apply_identical ? 1 : 0, e.payload_iq_identical ? 1 : 0,
                        e.recovered_stream_identical ? 1 : 0,
                        e.classification_window_identical ? 1 : 0,
                        e.model_input_identical ? 1 : 0, e.payload_sha.c_str(),
                        e.payload_iq_sha.c_str(), e.stream_sha.c_str(), e.window_sha.c_str(),
                        e.model_input_sha.c_str(), all_ok ? "PASS" : "FAIL");
            return all_ok ? 0 : 1;
        }

        if (wide_linear_self_test) {
            const replay24force::WideLinearSelfTestResult w =
                replay24force::run_wide_linear_self_test();
            const bool all_ok = w.apply_equivalent && w.roundtrip_corr_ok &&
                                w.image_ratio_ok && w.wl_beats_scalar;
            std::printf("FIX10CLASS24_FORCE_CLASSIFY_WIDE_LINEAR_SELF_TEST "
                        "apply_equivalent=%d roundtrip_corr_ok=%d image_ratio_ok=%d "
                        "wl_beats_scalar=%d scalar_corr=%.9f wide_linear_corr=%.9f "
                        "image_ratio=%.9f image_ratio_expected=%.9f residual_before=%.9f "
                        "result=%s\n",
                        w.apply_equivalent ? 1 : 0, w.roundtrip_corr_ok ? 1 : 0,
                        w.image_ratio_ok ? 1 : 0, w.wl_beats_scalar ? 1 : 0,
                        w.scalar_corr, w.wide_linear_corr, w.image_ratio,
                        w.image_ratio_expected, w.residual_before,
                        all_ok ? "PASS" : "FAIL");
            return all_ok ? 0 : 1;
        }

        if (decompose) {
            if (dump_dir.empty())
                throw std::runtime_error("--decompose requires --dump-dir");
            const std::string cap = basename(dirname(dirname(dump_dir)));
            const std::string idx = basename(dump_dir);
            if (cap == "." || cap.empty() || idx == "." || idx.empty())
                throw std::runtime_error("cannot derive capture_id/source_index from --dump-dir");
            source_index = std::stoll(idx);

            const replay24force::ResidualDecomposition r =
                replay24force::decompose_residual(dump_dir, cap, source_index);
            if (!r.reconstruction_consistent)
                throw std::runtime_error(
                    "residual decomposition reconstruction inconsistent with canonical replay");

            auto cand = [&](const std::string& name) -> const replay24force::ResidualDecomposition::Cand& {
                for (const auto& c : r.candidates)
                    if (c.name == name) return c;
                throw std::runtime_error("missing candidate " + name);
            };
            const auto& cp = cand("const_phase");
            const auto& rc = cand("residual_cfo");
            const auto& wl = cand("wide_linear");
            const auto& fir = cand("fir5");

            // TSV row (24 cols) -> stdout; human line -> stderr.
            std::printf("%s\t%lld\t%.9g\t%.9g\t%.9g\t"
                        "%.9g\t%.9g\t%.9g\t%.9g\t"
                        "%.9g\t%.9g\t%.9g\t%.9g\t%.9g\t"
                        "%.9g\t%.9g\t%.9g\t%.9g\t%.9g\t"
                        "%.9g\t%.9g\t%.9g\t%.9g\t%s\n",
                        r.capture_id.c_str(), r.source_index,
                        r.residual_before, r.residual_before_validation, r.corr_before,
                        cp.residual_after_train, cp.residual_after_validation,
                        cp.corr_after_validation, cp.improvement_ratio,
                        rc.residual_after_train, rc.residual_after_validation,
                        rc.corr_after_validation, rc.improvement_ratio, r.residual_cfo_hz,
                        wl.residual_after_train, wl.residual_after_validation,
                        wl.corr_after_validation, wl.improvement_ratio,
                        r.wide_linear_image_ratio,
                        fir.residual_after_train, fir.residual_after_validation,
                        fir.corr_after_validation, fir.improvement_ratio,
                        r.attribution.c_str());
            std::fprintf(stderr,
                         "RESIDUAL_DECOMPOSE capture_id=%s source_index=%lld residual_before=%.9f "
                         "corr_before=%.9f const_phase_imp=%.6f residual_cfo_imp=%.6f (df=%.3f Hz) "
                         "wide_linear_imp=%.6f (image_ratio=%.4g) fir5_imp=%.6f attribution=%s\n",
                         r.capture_id.c_str(), r.source_index, r.residual_before, r.corr_before,
                         cp.improvement_ratio, rc.improvement_ratio, r.residual_cfo_hz,
                         wl.improvement_ratio, r.wide_linear_image_ratio,
                         fir.improvement_ratio, r.attribution.c_str());
            std::fflush(stdout);
            std::fflush(stderr);
            return 0;
        }

        if (dump_dir.empty() || clean24_dir.empty() || export_dir.empty())
            throw std::runtime_error(
                "usage: replay_fix10class24_failed_rx_force_classify --self-test "
                "--clean24-dir DIR [--source-index N] | --dump-dir DIR --clean24-dir DIR "
                "--export-dir DIR");

        // capture_id = the round directory (dump_dir == <capture_id>/failed_rx/<idx>).
        const std::string capture_id = basename(dirname(dirname(dump_dir)));
        const std::string idx = basename(dump_dir);
        if (capture_id == "." || capture_id.empty() || idx == "." || idx.empty())
            throw std::runtime_error("cannot derive capture_id/source_index from --dump-dir");
        source_index = std::stoll(idx);

        const replay24force::ForceClassifyResult r =
            replay24force::force_classify_from_dir(dump_dir, clean24_dir, capture_id,
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
        replay24force::write_export(export_dir, r);

        const bool canonical_ok =
            r.timing_ok && r.coarse_ok && r.fine_ok && r.corr_ok && r.resid_ok;
        std::printf("FIX10CLASS24_FORCE_CLASSIFY capture_id=%s source_index=%lld "
                    "source_class=%d residual=%.9f corr=%.9f canonical_crosscheck=%s "
                    "reconstruction_consistent=%d model_input_finite=%s "
                    "model_input_sha=%s wide_linear_applicable=%d wide_linear_reason=%s "
                    "wide_linear_image_ratio=%.9g wide_linear_model_input_sha=%s\n",
                    r.capture_id.c_str(), r.source_index, r.source_class,
                    r.payload_training_residual, r.payload_training_corr,
                    canonical_ok ? "PASS" : "FAIL",
                    r.reconstruction_consistent ? 1 : 0,
                    "see_json", r.chain.cw.aligned_sha256.c_str(),
                    r.wide_linear_applicable ? 1 : 0, r.wide_linear_reason.c_str(),
                    r.wide_linear_image_ratio,
                    r.wide_linear_applicable
                        ? r.chain_wide_linear.cw.aligned_sha256.c_str()
                        : "(n/a)");
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "replay_fix10class24_failed_rx_force_classify: ERROR: %s\n",
                     e.what());
        return 2;
    }
}
