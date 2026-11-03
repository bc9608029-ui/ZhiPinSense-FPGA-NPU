// pilot1_capture_runner_syntax.cpp -- compile-only (-fsyntax-only) coverage for the FULL
// M29-RML24-REALRF-FINETUNE-PILOT1 board capture runner
// (board_package/pilot1_capture_runner.hpp).
//
// The pure host tests (test_pilot1_capture.cpp / pilot1_e2e_sim.cpp) deliberately do NOT
// compile the runner: it pulls in pluto devices + the TCP TX-control channel + the NPU,
// which are board-only.  That gap let a declaration-order bug (ok_pred() used before its
// definition) slip through the 38/0 host suite.  This TU closes it: it transitively
// includes the FULL runner under the iCraft headers, so -fsyntax-only catches any
// use-before-declaration / type / template-instantiation error in the runner itself
// before a board aarch64 build is attempted.
//
// This file is compiled ONLY by host_tests/syntax_check.sh (never linked or run on host;
// the runner is a board-only code path).
#include "../board_package/pilot1_capture_runner.hpp"

int main() { return 0; }
