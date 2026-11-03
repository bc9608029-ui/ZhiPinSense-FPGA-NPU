// syntax_runner_template.cpp -- fix2 B-line: force-instantiate the full runner template
// so the template body (sync/recovery/control timers, first_res move) is semantically
// checked on the host even though the host test never calls run_radioml_independent_rx.
// Compiled with -fsyntax-only (the board-only symbols never need to LINK).

#include "../board_package/radioml_independent_rx_runner.hpp"

#include <functional>
#include <vector>

namespace {
struct MockNpu2 {
    void infer(const float*, std::vector<float>& out) { out.assign(24, 0.0f); }
};
}  // namespace

// Explicit instantiation -> forces the template body to be compiled/checked.
template iqindepfix1::IndependentRxRunReport
iqindepfix1::run_radioml_independent_rx<MockNpu2>(
    MockNpu2&, m22::StageTiming&, int, char**,
    const std::function<void(const rf::ResultFrame&)>&);
