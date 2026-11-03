// test_display_diagnostic.cpp -- host tests for the M18-0 display root-cause
// diagnostic logic (board_display_diagnostic's pure core) and the two purely-
// additive backend methods it relies on: submit_frame_no_flip (Tool B) and
// read_frame_words (Tool D).  No /dev/udmabuf0 or /dev/mem is touched; the backend
// is driven through the same mock Io as test_display_integrity.cpp.
//
// Proves on the host, before any board test:
//   * mode parsing (a/b/c/d + long spellings) is fail-closed;
//   * CRC-32 matches the standard IEEE 802.3 test vector (0xCBF43926), so Tool D's
//     pre/post comparison is trustworthy;
//   * crc32_u16 equals crc32 over the raw little-endian byte stream, so a board
//     mapping and a host buffer give the same CRC;
//   * fill_solid fills exactly `words` and leaves the tail untouched;
//   * submit_frame_no_flip copies + flushes but NEVER writes the buffer-select
//     register (the single-buffer lock is real, not cosmetic);
//   * read_frame_words reads the device mapping back verbatim (the CRC read-back
//     is real, not a copy of the staging buffer).

#include "../ui_sw/direct_framebuffer_backend.hpp"
#include "../ui_sw/display_diagnostic.hpp"

#include <cstdio>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;
void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

struct MockIo : dfb::Io {
    std::uint64_t phys = 0;
    std::uint64_t capacity = 0;
    std::uint32_t version = 0;
    std::vector<std::uint16_t> fb;   // total_bytes()/2 RGB565 words
    std::vector<std::uint32_t> mem;  // 0x1000/4 registers

    std::string read_text(const std::string& path) override {
        if (path.find("phys_addr") != std::string::npos) return "0x" + hex(phys);
        if (path.find("size") != std::string::npos) return std::to_string(capacity);
        return "";
    }
    int open_dev(const std::string&, int) override { return 10; }
    void* map(int, std::size_t, std::uint64_t offset) override {
        if (offset == 0) return fb.data();
        return mem.data();
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

void test_mode_parse() {
    ddx::Mode m = ddx::Mode::D_CrcCheck;
    check(ddx::parse_mode("a", &m) && m == ddx::Mode::A_BlackClearStatic, "parse a");
    check(ddx::parse_mode("A", &m) && m == ddx::Mode::A_BlackClearStatic, "parse A");
    check(ddx::parse_mode("black-clear", &m) && m == ddx::Mode::A_BlackClearStatic, "parse black-clear");
    check(ddx::parse_mode("black_clear", &m) && m == ddx::Mode::A_BlackClearStatic, "parse black_clear");
    check(ddx::parse_mode(" b ", &m) && m == ddx::Mode::B_SingleBufferLock, "parse ' b ' ws");
    check(ddx::parse_mode("single-buffer", &m) && m == ddx::Mode::B_SingleBufferLock, "parse single-buffer");
    check(ddx::parse_mode("c", &m) && m == ddx::Mode::C_RedBlueSwitch, "parse c");
    check(ddx::parse_mode("red-blue", &m) && m == ddx::Mode::C_RedBlueSwitch, "parse red-blue");
    check(ddx::parse_mode("red_blue", &m) && m == ddx::Mode::C_RedBlueSwitch, "parse red_blue");
    check(ddx::parse_mode("d", &m) && m == ddx::Mode::D_CrcCheck, "parse d");
    check(ddx::parse_mode("CRC", &m) && m == ddx::Mode::D_CrcCheck, "parse CRC");

    m = ddx::Mode::A_BlackClearStatic;
    check(!ddx::parse_mode("e", &m), "reject e");
    check(!ddx::parse_mode("", &m), "reject empty");
    check(!ddx::parse_mode("  ", &m), "reject blank");
    check(!ddx::parse_mode("ab", &m), "reject ab");
    check(!ddx::parse_mode("black_clea", &m), "reject near-miss");
    check(m == ddx::Mode::A_BlackClearStatic, "rejected parse leaves out unchanged");

    check(std::string(ddx::mode_name(ddx::Mode::A_BlackClearStatic)) == "a", "mode_name a");
    check(std::string(ddx::mode_name(ddx::Mode::B_SingleBufferLock)) == "b", "mode_name b");
    check(std::string(ddx::mode_name(ddx::Mode::C_RedBlueSwitch)) == "c", "mode_name c");
    check(std::string(ddx::mode_name(ddx::Mode::D_CrcCheck)) == "d", "mode_name d");
}

void test_crc() {
    // Standard IEEE 802.3 CRC-32 check value for the ASCII digits 1..9.
    check(ddx::crc32("123456789", 9) == 0xCBF43926u, "crc32 test vector 0xCBF43926");
    check(ddx::crc32("", 0) == 0x00000000u, "crc32 empty -> 0");

    // crc32_u16 == crc32 over the raw in-memory little-endian byte stream.
    const std::uint16_t words[3] = {0x1234u, 0xABCDu, 0x0000u};
    const std::uint8_t bytes[6] = {0x34u, 0x12u, 0xCDu, 0xABu, 0x00u, 0x00u};
    check(ddx::crc32_u16(words, 3) == ddx::crc32(bytes, sizeof(bytes)),
          "crc32_u16 equals byte-stream crc32");

    // Solid-buffer CRC is deterministic and differs across colours.
    std::vector<std::uint16_t> buf(16, ddx::kRed);
    const std::uint32_t red = ddx::crc32_u16(buf.data(), buf.size());
    ddx::fill_solid(buf.data(), buf.size(), ddx::kBlue);
    const std::uint32_t blue = ddx::crc32_u16(buf.data(), buf.size());
    check(red != blue, "red and blue CRCs differ");
    check(red == ddx::crc32_u16(std::vector<std::uint16_t>(16, ddx::kRed).data(), 16),
          "solid-red CRC deterministic");
}

void test_fill_solid() {
    std::vector<std::uint16_t> buf(8, 0xFFFFu);
    ddx::fill_solid(buf.data(), 3, ddx::kGreen);
    check(buf[0] == ddx::kGreen && buf[1] == ddx::kGreen && buf[2] == ddx::kGreen,
          "fill_solid fills first 3");
    check(buf[3] == 0xFFFFu && buf[7] == 0xFFFFu, "fill_solid leaves tail untouched");
}

void test_backend_diagnostic_methods() {
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

    // Fail-closed before init.
    check(!fb.submit_frame_no_flip(0, io.fb.data(), words), "no_flip before init fails");
    std::vector<std::uint16_t> tmp(words, 0);
    check(!fb.read_frame_words(0, tmp.data(), words), "read_frame_words before init fails");

    check(fb.init(), "init ok");
    check(fb.ready(), "ready after init");

    // submit_frame_no_flip copies + flushes but never writes buffer-select.
    std::vector<std::uint16_t> stage(words, 0x1234u);
    check(fb.submit_frame_no_flip(0, stage.data(), words), "submit_frame_no_flip(0) ok");
    check(io.fb[0] == 0x1234u && io.fb[words - 1] == 0x1234u, "frame 0 received pixels");
    check(io.fb[words] == 0xFFFFu, "frame 1 untouched by no_flip(0)");
    check(io.mem[cfg.wr_addr_offset / 4] == 0u, "no_flip NEVER writes buffer-select register");

    // read_frame_words reads the device mapping back verbatim.
    std::vector<std::uint16_t> readback(words, 0xDEADu);
    check(fb.read_frame_words(0, readback.data(), words), "read_frame_words(0) ok");
    check(readback[0] == 0x1234u && readback[words - 1] == 0x1234u,
          "read-back matches written device content");
    check(readback[0] == io.fb[0], "read-back is the device mapping, not the staging buffer");

    // Out-of-range / bad args fail closed.
    check(!fb.submit_frame_no_flip(2, stage.data(), words), "no_flip frame_index 2 fails");
    check(!fb.submit_frame_no_flip(-1, stage.data(), words), "no_flip frame_index -1 fails");
    check(!fb.submit_frame_no_flip(0, nullptr, words), "no_flip null staging fails");
    check(!fb.submit_frame_no_flip(0, stage.data(), 0), "no_flip zero count fails");
    check(!fb.read_frame_words(2, readback.data(), words), "read_frame_words index 2 fails");
    check(!fb.read_frame_words(0, nullptr, words), "read_frame_words null dst fails");
    check(!fb.read_frame_words(0, readback.data(), words + 1), "read_frame_words over-count fails");
}

}  // namespace

int main() {
    std::printf("test_display_diagnostic\n");
    test_mode_parse();
    test_crc();
    test_fill_solid();
    test_backend_diagnostic_methods();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
