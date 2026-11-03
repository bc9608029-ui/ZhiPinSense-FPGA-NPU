#include "../fix10class24_fix1v2_board_impl1_work/board_package/radioml_independent_rx_runner.hpp"
#include <iostream>

// This review executable is strictly file-only. Device access is forbidden.
namespace pluto {
Device* make_device(const std::string&) { throw std::runtime_error("review forbids hardware"); }
}
struct ReviewNpu {
    int calls = 0;
    void infer(const float*, std::vector<float>& out) {
        ++calls;
        out.assign(24, 0.0f);
        out[0] = 1.0f;
    }
};
int main(int argc, char** argv) {
    if (argc != 3) return 2;
    const std::string tx = argv[1], scratch = argv[2];
    auto frames = iqindepfix1::load_independent_rx_manifest(tx + "/public_protocol_tx_manifest.tsv");
    std::vector<std::int16_t> raw;
    std::string err;
    if (!iqindepfix1::read_i16_file(tx + "/" + frames[0].burst_file, raw, &err)) return 3;
    auto rx = iqrftrain::deinterleave(raw);
    ReviewNpu npu;
    const auto result = iqindepfix1::recover_and_classify_one(
        npu, rx, frames[0], frames[0].unscale, scratch,
        false, false, true, "review-only");
    std::cout << "BAD_CAPTURE_CLIPPED gated=" << result.gated
              << " finite=" << result.finite << " infer_calls=" << npu.calls << "\n";
    std::vector<std::int16_t> railed(2048, 2047);
    std::cout << "ADC_12BIT_POSITIVE_RAIL clip_ratio=" << iqindepfix1::clip_ratio(railed) << "\n";
    std::vector<std::string> args = {"review", "--input-dir=" + tx,
        "--out-dir=" + scratch + "/file_run", "--capture-source=file"};
    std::vector<char*> ptrs;
    for (auto& arg : args) ptrs.push_back(arg.data());
    m22::StageTiming timing;
    auto rep = iqindepfix1::run_radioml_independent_rx(
        npu, timing, static_cast<int>(ptrs.size()), ptrs.data(), [](const rf::ResultFrame&) {});
    std::cout << "FILE_RUN completed=" << rep.completed << " processed=" << rep.n_processed
              << " readback=" << rep.rx_readback_ok << " negative=" << rep.negative_control_pass
              << " functional_pass=" << rep.functional_pass << "\n";
    args[2] = "--out-dir=" + scratch;
    ptrs.clear();
    for (auto& arg : args) ptrs.push_back(arg.data());
    try {
        iqindepfix1::run_radioml_independent_rx(npu, timing, static_cast<int>(ptrs.size()), ptrs.data(),
                                             [](const rf::ResultFrame&) {});
    } catch (const std::exception& e) {
        std::cout << "PRECREATED_OUT " << e.what() << "\n";
    }
}
