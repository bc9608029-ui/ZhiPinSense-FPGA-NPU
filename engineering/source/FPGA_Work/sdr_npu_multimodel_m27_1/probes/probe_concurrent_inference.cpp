// probe_concurrent_inference.cpp — M27.1 concurrency probe.
//
// The iCraft 3.39 XRT runtime has NO Job class and NO async-submit/queue API
// (see docs/M27_1_SDK_MULTI_MODEL_AUDIT.md §7): Session::forward() is a single
// synchronous completion-handshake, and Backend::fork() only copies a backend
// "for multithreading" — it does not claim multi-model parallel execution.
// Under task safety rule "API 不允许的调用不得强行测试", this probe therefore
// does NOT fabricate a concurrency experiment.  It records the API finding and
// exits with SKIP; true concurrent execution stays UNVERIFIED until an SDK that
// documents async submission is present.
//
// Usage:
//   probe_concurrent_inference --out result.json

#include "probe_common.hpp"

#include <cstdio>
#include <string>

using namespace m27_1;

int main(int argc, char** argv) {
    ProbeResult r;
    r.probe = "probe_concurrent_inference";
    r.status = "SKIP";
    r.conclusion = "CONCURRENT_UNSUPPORTED_BY_API";
    r.notes =
        "iCraft 3.39 XRT has no Job/async-submit API (audit section 7); "
        "concurrent execution is not testable via a documented API and is left "
        "UNVERIFIED per task rule 'API not allowed must not be force-tested'.";

    const std::string out = arg_value(argc, argv, "--out");
    if (out.empty()) {
        // Still emit the tail marker so the one-click script sees SKIP, not a hang.
        std::fputs(r.to_json().c_str(), stdout);
        emit_tail("SKIP", "");
        return 0;
    }
    FILE* f = std::fopen(out.c_str(), "w");
    if (!f) { std::fprintf(stderr, "cannot write result json\n"); return 1; }
    std::fputs(r.to_json().c_str(), f);
    std::fclose(f);
    emit_tail("SKIP", out);
    return 0;
}
