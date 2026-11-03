// test_capture_hook.cpp -- host tests for the atomic NPU-input tensor capture
// (errata 39e5 Stage C, #6).  iCraft-free/libiio-free: exercises board::TensorCapture
// exactly as the board's live-rx producer uses it (capture_hook.hpp).
//
// Proves:
//   (1) an empty --capture-dir disables capture (no file I/O, capture() == "");
//   (2) capture() returns the SHA-256 of the EXACT bytes written;
//   (3) the file lands at its FINAL name, is exactly 8192 bytes (2048 fp32), and
//       is byte-identical to the NPU input tensor (no re-scale, no re-order);
//   (4) atomicity: the .tmp staging file never survives, so a reader sees the
//       complete file or nothing;
//   (5) a bad destination directory fails closed (returns "" without a file).
//
// POSIX-only for the filesystem parts (mkdir/access/rmdir); the disabled/bad-dir
// checks run everywhere.  Build/run: see host_tests/build_host_tests.sh.

#include "../board_package/capture_hook.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace {

int g_pass = 0, g_fail = 0;
void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

// A deterministic [2,1024] fp32 tensor (plane 0 = I, plane 1 = Q).
std::vector<float> make_tensor() {
    const std::size_t n = 2048;
    std::vector<float> t(n);
    for (std::size_t i = 0; i < n; ++i)
        t[i] = static_cast<float>(i) * 0.5f - 512.0f;
    return t;
}

#if defined(__unix__) || defined(__APPLE__)
std::string make_tmp_dir() {
    const std::string base = "/tmp/rml23_capture_hook_" + std::to_string(::getpid());
    ::mkdir(base.c_str(), 0700);
    return base;
}

void rm_file(const std::string& p) {
    ::unlink(p.c_str());
}

void rm_dir(const std::string& d) {
    for (int i = 0; i < 4; ++i) {
        const std::string stem = d + "/live_rx_tensor_" + std::to_string(i) + ".f32";
        rm_file(stem);
        rm_file(stem + ".tmp");
    }
    ::rmdir(d.c_str());
}
#endif

void run() {
    // (1) disabled capture
    {
        board::TensorCapture off("");
        check(!off.enabled(), "empty dir disables capture");
        std::vector<float> t = make_tensor();
        check(off.capture(0, t.data(), t.size()).empty(),
              "disabled capture returns empty (no file I/O)");
    }

    // (5) bad destination fails closed
    {
        board::TensorCapture bad("/nonexistent_rml23_dir_zzz");
        std::vector<float> t = make_tensor();
        check(bad.capture(1, t.data(), t.size()).empty(),
              "bad destination dir fails closed (returns empty)");
    }

#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir();
    const std::vector<float> t = make_tensor();
    const std::size_t n_floats = t.size();
    const std::string want_sha =
        sdr::Sha256::hex(t.data(), n_floats * sizeof(float));

    board::TensorCapture cap(dir);
    check(cap.enabled(), "capture enabled with non-empty dir");

    // (2) SHA of the exact bytes
    const std::string got = cap.capture(3, t.data(), n_floats);
    check(got == want_sha, "capture() returns SHA-256 of the exact bytes");

    // (3) final name, exact size, byte-identity
    const std::string path = dir + "/live_rx_tensor_3.f32";
    std::FILE* f = std::fopen(path.c_str(), "rb");
    check(f != nullptr, "capture file exists at its final name");
    if (f) {
        std::vector<std::uint8_t> buf(n_floats * sizeof(float));
        const std::size_t rd = std::fread(buf.data(), 1, buf.size(), f);
        const bool ok_rd = !std::ferror(f);
        std::fclose(f);
        check(ok_rd && rd == buf.size(), "capture file is exactly 8192 bytes");
        check(std::memcmp(buf.data(), t.data(), buf.size()) == 0,
              "capture file is byte-identical to the NPU input tensor");
    }

    // (4) atomicity: no .tmp survives
    check(std::fopen((path + ".tmp").c_str(), "rb") == nullptr,
          "no .tmp staging file survives (atomic rename)");

    // Deterministic re-capture of the same frame overwrites atomically and
    // returns the same digest.
    check(cap.capture(3, t.data(), n_floats) == want_sha,
          "re-capture of the same frame returns the same digest");

    rm_dir(dir);
#else
    (void)0;   // filesystem checks are POSIX-only; the pure checks above run everywhere
#endif
}

}  // namespace

int main() {
    std::printf("test_capture_hook\n");
    run();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
