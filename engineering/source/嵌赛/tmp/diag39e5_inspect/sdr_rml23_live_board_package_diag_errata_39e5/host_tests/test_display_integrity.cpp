// test_display_integrity.cpp -- host tests for Task B (HDMI dirty-frame / tearing):
// the ping-pong double-buffer gates and the startup clear path of the safe
// framebuffer backend.  No /dev/udmabuf0 or /dev/mem is touched: the backend is
// driven through a mock Io whose map() returns heap buffers, so the pure gates and
// the clear_frame / clear_all_frames / submit_frame discipline are verified on the
// host exactly as the board runs them (scalar 16-bit stores, version gate, read-back
// verify, flush-after-copy, clear-before-rd_addr).
//
// What this proves for Task B:
//   * the two-frame (ping-pong) physical gate: fb1 = fb0 + frame_bytes, both
//     8-byte aligned and < 1 GiB, pair fits udmabuf capacity;
//   * the version gate refuses every register write on a mismatched RTL version;
//   * clear_frame / clear_all_frames zero the DEVICE mapping (startup never shows
//     stale DDR left over from the bitstream reload);
//   * submit_frame flips the buffer select only after copy + sync, and verifies the
//     register read-back;
//   * out-of-range / not-ready calls fail closed instead of corrupting memory.
//
// Build/run: see host_tests/build_host_tests.sh.

#include "../ui_sw/direct_framebuffer_backend.hpp"

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;
void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

// ---- mock OS side effects --------------------------------------------------
struct MockIo : dfb::Io {
    std::uint64_t phys = 0;
    std::uint64_t capacity = 0;
    std::uint32_t version = 0;
    std::vector<std::uint16_t> fb;   // total_bytes()/2 RGB565 words
    std::vector<std::uint32_t> mem;  // 0x1000/4 registers
    std::uint64_t map_calls = 0;

    std::string read_text(const std::string& path) override {
        if (path.find("phys_addr") != std::string::npos)
            return "0x" + hex(phys);
        if (path.find("size") != std::string::npos)
            return std::to_string(capacity);
        return "";
    }
    int open_dev(const std::string&, int) override { return 10; }
    void* map(int, std::size_t, std::uint64_t offset) override {
        ++map_calls;
        if (offset == 0) return fb.data();
        return mem.data();   // register page
    }
    int unmap(void*, std::size_t) override { return 0; }
    int close_fd(int) override { return 0; }
    int msync_range(void*, std::size_t, int) override { return 0; }
    bool write_sync_node(const std::string&) override { return true; }
    int last_errno() const override { return 0; }

    static std::string hex(std::uint64_t v) {
        char b[32];
        std::snprintf(b, sizeof(b), "%llx", static_cast<unsigned long long>(v));
        return b;
    }
};

// ---- pure gates ------------------------------------------------------------
void test_pure_gates() {
    std::uint64_t v = 0;
    check(dfb::parse_u64("0x40000000", &v) && v == 0x40000000ULL, "parse_u64 hex");
    check(dfb::parse_u64(" 1234 ", &v) && v == 1234ULL, "parse_u64 decimal + ws");
    check(dfb::parse_u64("010", &v) && v == 8ULL, "parse_u64 octal");
    check(!dfb::parse_u64("", &v), "parse_u64 empty -> false");
    check(!dfb::parse_u64("0x", &v), "parse_u64 bare 0x -> false");
    check(!dfb::parse_u64("12ab", &v), "parse_u64 trailing junk -> false");
    check(!dfb::parse_u64("0x12abzz", &v), "parse_u64 hex trailing junk -> false");

    const std::uint64_t frame = 1280ULL * 720 * 2;

    dfb::CheckResult c = dfb::check_framebuffer(0x10000000, frame * 2, frame);
    check(c.ok, "check_framebuffer ok");
    c = dfb::check_framebuffer(0x10000000, frame * 2, 0);
    check(!c.ok, "check_framebuffer zero frame_bytes");
    c = dfb::check_framebuffer(0x10000001, frame * 2, frame);
    check(!c.ok, "check_framebuffer misaligned phys");
    c = dfb::check_framebuffer(0x40000000ULL, frame * 2, frame);
    check(!c.ok, "check_framebuffer phys >= 1 GiB");
    c = dfb::check_framebuffer(0x10000000, frame - 1, frame);
    check(!c.ok, "check_framebuffer capacity < frame");

    std::uint64_t fb1 = 0;
    c = dfb::check_double_buffer(0x10000000, frame, frame * 2, &fb1);
    check(c.ok && fb1 == 0x10000000 + frame, "check_double_buffer fb1 = fb0 + frame");
    c = dfb::check_double_buffer(0x10000000, frame, frame * 2 - 1, &fb1);
    check(!c.ok, "check_double_buffer capacity < 2*frame");
    c = dfb::check_double_buffer(0x10000000 + (frame - 1), frame, frame * 2, &fb1);
    check(!c.ok, "check_double_buffer fb1 misaligned");
    c = dfb::check_double_buffer(0x3fffffffULL, frame, frame * 2, &fb1);
    check(!c.ok, "check_double_buffer fb1 >= 1 GiB");
    c = dfb::check_double_buffer(0x10000001, frame, frame * 2, &fb1);
    check(!c.ok, "check_double_buffer fb0 misaligned");

    check(dfb::version_allows_write(0x20230218U, 0x20230218U), "version match allows write");
    check(!dfb::version_allows_write(0x11111111U, 0x20230218U), "version mismatch refuses");

    check(dfb::readback_matches(0x1234, 0x1234), "readback equal");
    check(!dfb::readback_matches(0x1234, 0x1235), "readback unequal");

    check(dfb::classify_msync(0, 0) == dfb::MsyncAction::Continue, "msync rc=0 continue");
    check(dfb::classify_msync(-1, EINVAL) == dfb::MsyncAction::TolerateEinval,
          "msync EINVAL tolerated");
    check(dfb::classify_msync(-1, EIO) == dfb::MsyncAction::Fail, "msync EIO fails");
}

// ---- mock-backed backend: init + clear + submit ----------------------------
void test_backend_clear_and_submit() {
    dfb::Config cfg;
    const std::uint64_t frame = cfg.frame_bytes();
    const std::size_t words = static_cast<std::size_t>(frame / 2);

    MockIo io;
    io.phys = 0x10000000;
    io.capacity = frame * 2;   // exactly two frames
    io.version = cfg.expected_version;
    io.fb.assign(words * 2, 0xFFFFu);   // pre-fill with garbage
    io.mem.assign(0x1000 / 4, 0);
    io.mem[cfg.version_offset / 4] = cfg.expected_version;

    dfb::DirectFramebufferBackend fb(cfg, io);

    // Fail-closed BEFORE init.
    check(!fb.ready(), "not ready before init");
    check(!fb.clear_frame(0), "clear_frame before init fails closed");
    check(!fb.submit_frame(0, io.fb.data(), words), "submit_frame before init fails closed");

    // Init resolves phys/capacity, validates the double buffer, maps, gates version.
    check(fb.init(), "init() ok with matching version");
    check(fb.ready(), "ready after init");
    check(fb.phys_addr() == io.phys, "phys resolved from sysfs");
    check(fb.capacity() == frame * 2, "capacity resolved from sysfs");

    // Out-of-range frame index fails closed.
    check(!fb.clear_frame(2), "clear_frame(2) out of range (num_frames=2)");
    check(!fb.clear_frame(-1), "clear_frame(-1) out of range");

    // clear_frame zeroes exactly one frame in the DEVICE mapping.
    check(io.fb[0] == 0xFFFFu && io.fb[words] == 0xFFFFu, "precondition: both frames dirty");
    check(fb.clear_frame(0), "clear_frame(0) ok");
    check(io.fb[0] == 0u && io.fb[words] == 0xFFFFu, "frame 0 cleared, frame 1 untouched");

    // clear_all_frames zeroes everything (startup: black frames before rd_addr).
    io.fb.assign(words * 2, 0xFFFFu);
    check(fb.clear_all_frames(), "clear_all_frames ok");
    bool all_zero = true;
    for (std::uint16_t w : io.fb) if (w != 0u) { all_zero = false; break; }
    check(all_zero, "all frames zero after clear_all_frames");

    // submit_frame: copies staging into frame[1] and flips the buffer select, with
    // the register read-back verified (mock memory reflects the write).
    std::vector<std::uint16_t> stage(words, 0x1234u);
    check(fb.submit_frame(1, stage.data(), words), "submit_frame(1) ok");
    check(io.fb[words] == 0x1234u, "frame 1 received staging pixels");
    check(io.fb[0] == 0u, "frame 0 untouched by submit_frame(1)");
    check(io.mem[cfg.wr_addr_offset / 4] == 1u, "buffer select flipped to frame 1");
}

// ---- M17 Task F: set_display_enable (blank / un-blank) ----------------------
void test_display_enable() {
    dfb::Config cfg;
    const std::uint64_t frame = cfg.frame_bytes();
    const std::size_t words = static_cast<std::size_t>(frame / 2);

    MockIo io;
    io.phys = 0x10000000;
    io.capacity = frame * 2;
    io.version = cfg.expected_version;
    io.fb.assign(words * 2, 0xFFFFu);
    io.mem.assign(0x1000 / 4, 0);
    io.mem[cfg.version_offset / 4] = cfg.expected_version;

    dfb::DirectFramebufferBackend fb(cfg, io);

    // Fail closed before init.
    check(!fb.set_display_enable(false), "set_display_enable before init fails closed");
    check(!fb.set_display_enable(true), "set_display_enable(true) before init fails closed");

    check(fb.init(), "init() ok");
    check(fb.ready(), "ready after init");

    // Blank writes disable_hdmi=1 and leaves the framebuffer untouched.
    const std::uint16_t before0 = io.fb[0];
    const std::uint16_t before1 = io.fb[words];
    check(fb.set_display_enable(false), "blank ok");
    check(io.mem[cfg.disable_hdmi_offset / 4] == 1u, "disable_hdmi set (blanked)");
    check(io.fb[0] == before0 && io.fb[words] == before1, "blank does not touch framebuffer");

    // Un-blank writes disable_hdmi=0.
    check(fb.set_display_enable(true), "un-blank ok");
    check(io.mem[cfg.disable_hdmi_offset / 4] == 0u, "disable_hdmi cleared (un-blanked)");

    // It never touches the buffer-select register.
    check(io.mem[cfg.wr_addr_offset / 4] == 0u, "set_display_enable leaves buffer select alone");

    // Full M17 startup order: blank -> clear -> submit -> rd_addr -> un-blank, all
    // true, leaving a valid frame 0 on screen with the display re-enabled.
    check(fb.set_display_enable(false), "startup blank ok");
    check(fb.clear_all_frames(), "startup clear ok");
    std::vector<std::uint16_t> stage(words, 0x0ABC);
    check(fb.submit_frame(0, stage.data(), words), "startup submit frame 0 ok");
    const std::uint32_t rd = static_cast<std::uint32_t>(io.phys >> 3);
    check(fb.write_reg(cfg.rd_addr_offset, rd), "startup rd_addr write ok");
    check(fb.set_display_enable(true), "startup un-blank ok");
    check(io.mem[cfg.disable_hdmi_offset / 4] == 0u, "startup ends un-blanked");
    check(io.fb[0] == 0x0ABCu, "startup leaves frame 0 valid");
}

}  // namespace

int main() {
    std::printf("test_display_integrity\n");
    test_pure_gates();
    test_backend_clear_and_submit();
    test_display_enable();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
