// test_direct_framebuffer_backend.cpp — host mock test for the safe HDMI backend.
//
// Builds and runs on an x86 Linux host (or WSL).  It does NOT need /dev/udmabuf0,
// /dev/mem, or any real hardware: every OS side effect is faked through a MockIo,
// and every path is injected through Config.  This proves the backend's
// validation and decision logic before it ever runs on the board.
//
//   g++ -std=gnu++17 -Wall -Wextra -O2
//       test_direct_framebuffer_backend.cpp direct_framebuffer_backend.cpp
//       -o test_direct_framebuffer_backend && ./test_direct_framebuffer_backend

#include "direct_framebuffer_backend.hpp"

#include <cerrno>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

namespace {

int g_fail = 0;

void expect(bool cond, const std::string& name) {
    if (cond) {
        std::cout << "  [ok] " << name << "\n";
    } else {
        std::cout << "  [FAIL] " << name << "\n";
        ++g_fail;
    }
}

// ---- MockIo: fakes every OS side effect --------------------------------
class MockIo : public dfb::Io {
public:
    std::string phys_text   = "0x30100000";
    std::string size_text   = "134217728";
    std::uint32_t mem_version = 0x20230218U;

    bool msync_einval = false;   // msync returns -1, errno=EINVAL
    bool msync_other  = false;   // msync returns -1, errno=EIO
    bool sync_present = true;

    int sync_calls = 0;
    std::string last_read_path;
    std::vector<std::string> read_paths;
    std::string last_sync_path;

    // backing stores handed back by map()
    std::vector<std::uint32_t> mem_store;
    std::vector<std::uint8_t> fb_store;

    std::string read_text(const std::string& path) override {
        last_read_path = path;
        read_paths.push_back(path);
        if (path.find("phys_addr") != std::string::npos) return phys_text;
        if (path.find("size") != std::string::npos) return size_text;
        throw std::runtime_error("MockIo: unexpected read " + path);
    }
    int open_dev(const std::string&, int) override { return 42; }
    void* map(int, std::size_t length, std::uint64_t offset) override {
        if (length == 0x1000 && offset == 0x40080000ULL) {
            mem_store.assign(length / 4, 0U);
            mem_store[0x0CU / 4] = mem_version;
            return mem_store.data();
        }
        fb_store.assign(length, 0);
        return fb_store.data();
    }
    int unmap(void*, std::size_t) override { return 0; }
    int close_fd(int) override { return 0; }
    int msync_range(void*, std::size_t, int) override {
        if (msync_einval) { errno_ = EINVAL; return -1; }
        if (msync_other)  { errno_ = EIO;    return -1; }
        return 0;
    }
    bool write_sync_node(const std::string& path) override {
        ++sync_calls;
        last_sync_path = path;
        return sync_present;
    }
    int last_errno() const override { return errno_; }

private:
    int errno_ = 0;
};

} // namespace

int main() {
    using namespace dfb;
    std::cout << std::unitbuf;   // flush each line so cout/cerr stay in order

    std::cout << "== parse_u64 (address parsing) ==\n";
    std::uint64_t v = 0;
    expect(parse_u64("0x30100000", &v) && v == 0x30100000ULL, "hex address");
    expect(parse_u64("134217728", &v) && v == 134217728ULL, "decimal size");
    expect(parse_u64("  0x30100000\n", &v) && v == 0x30100000ULL, "whitespace tolerated");
    expect(!parse_u64("", &v), "empty string rejected");
    expect(!parse_u64("zzz", &v), "garbage rejected");
    expect(!parse_u64("12abc", &v), "trailing garbage rejected");
    expect(!parse_u64("0x", &v), "bare 0x rejected");

    const std::uint64_t FB = 1280ULL * 720 * 2;   // 1,843,200

    std::cout << "== check_framebuffer (single-frame gate) ==\n";
    expect(check_framebuffer(0x30100000ULL, 134217728ULL, FB).ok, "valid base");
    expect(check_framebuffer(0x30100000ULL, FB, FB).ok, "capacity == frame (boundary ok)");
    expect(!check_framebuffer(0x30100000ULL, FB - 1, FB).ok, "capacity < frame (boundary fail)");
    expect(!check_framebuffer(1ULL, 134217728ULL, FB).ok, "1-byte address not aligned");
    expect(check_framebuffer(8ULL, 134217728ULL, FB).ok, "8-byte address aligned");
    expect(!check_framebuffer(1ULL << 30, 134217728ULL, FB).ok, "addr == 1 GiB rejected");
    expect(check_framebuffer((1ULL << 30) - 8, 134217728ULL, FB).ok, "addr just under 1 GiB ok");

    std::cout << "== check_double_buffer (ping-pong) ==\n";
    std::uint64_t fb1 = 0;
    expect(check_double_buffer(0x30100000ULL, FB, 134217728ULL, &fb1).ok
               && fb1 == 0x30100000ULL + FB, "FB1 = FB0 + frame_bytes");
    expect(check_double_buffer(0x30100000ULL, FB, 2 * FB, &fb1).ok, "capacity == 2 frames ok");
    expect(!check_double_buffer(0x30100000ULL, FB, 2 * FB - 1, &fb1).ok, "capacity < 2 frames fail");
    expect(!check_double_buffer((1ULL << 30) - FB, FB, 134217728ULL, &fb1).ok,
           "FB1 reaches 1 GiB rejected");

    std::cout << "== version / readback / msync gates ==\n";
    expect(version_allows_write(0x20230218U, 0x20230218U), "version match allows write");
    expect(!version_allows_write(0xDEADBEEFU, 0x20230218U), "version mismatch refuses write");
    expect(readback_matches(0x06020000U, 0x06020000U), "readback match");
    expect(!readback_matches(0x06020000U, 0x06020001U), "readback mismatch detected");
    expect(classify_msync(0, 0) == MsyncAction::Continue, "msync ok -> continue");
    expect(classify_msync(-1, EINVAL) == MsyncAction::TolerateEinval, "msync EINVAL tolerated");
    expect(classify_msync(-1, EIO) == MsyncAction::Fail, "msync other errno -> fail");

    std::cout << "== Backend integration (MockIo) ==\n";
    {
        Config cfg;
        cfg.sysfs_base = "/mock/sys/";   // prove path injectability
        MockIo io;
        DirectFramebufferBackend backend(cfg, io);

        expect(backend.init(), "init happy path");
        bool read_phys = false, read_size = false;
        for (const auto& p : io.read_paths) {
            if (p == "/mock/sys/phys_addr") read_phys = true;
            if (p == "/mock/sys/size") read_size = true;
        }
        expect(read_phys && read_size, "phys_addr/size read from injected sysfs base");
        expect(backend.phys_addr() == 0x30100000ULL, "phys_addr resolved from sysfs (not hardcoded)");
        expect(backend.capacity() == 134217728ULL, "capacity resolved from sysfs");
        expect(backend.ready(), "backend ready after init");

        expect(backend.write_reg(cfg.rd_addr_offset, 0x06020000U), "register write + readback ok");
        expect(backend.read_reg(cfg.rd_addr_offset) == 0x06020000U, "register value persists");
        expect(backend.write_reg(cfg.wr_addr_offset, 0U), "buffer-select write ok");

        expect(backend.flush(), "flush ok");
        expect(io.sync_calls == 1, "sync_for_device called once");
        expect(io.last_sync_path == cfg.sync_node, "sync node path correct");
    }

    std::cout << "== Backend: msync EINVAL tolerated ==\n";
    {
        Config cfg;
        MockIo io;
        io.msync_einval = true;
        DirectFramebufferBackend backend(cfg, io);
        expect(backend.init(), "init ok");
        expect(backend.flush(), "flush continues on EINVAL");
        expect(io.sync_calls == 1, "sync node still called after EINVAL");
    }

    std::cout << "== Backend: msync hard error fails ==\n";
    {
        Config cfg;
        MockIo io;
        io.msync_other = true;
        DirectFramebufferBackend backend(cfg, io);
        expect(backend.init(), "init ok");
        expect(!backend.flush(), "flush fails on non-EINVAL msync error");
    }

    std::cout << "== Backend: version mismatch refuses write ==\n";
    {
        Config cfg;
        MockIo io;
        io.mem_version = 0xDEADBEEFU;
        DirectFramebufferBackend backend(cfg, io);
        expect(!backend.init(), "init fails on version mismatch");
        expect(!backend.ready(), "backend not ready after version mismatch");
        // Nothing was written to the register space beyond the version read:
        expect(io.mem_store[0x54U / 4] == 0U, "no register write on version mismatch");
    }

    std::cout << "== Backend: bad phys rejected ==\n";
    {
        Config cfg;
        MockIo io;
        io.phys_text = "1";   // unaligned
        DirectFramebufferBackend backend(cfg, io);
        expect(!backend.init(), "init fails on unaligned phys");
    }
    {
        Config cfg;
        MockIo io;
        io.phys_text = "0x40000000";   // 1 GiB
        DirectFramebufferBackend backend(cfg, io);
        expect(!backend.init(), "init fails on phys >= 1 GiB");
    }

    std::cout << "\n" << (g_fail == 0 ? "ALL TESTS PASSED" : "SOME TESTS FAILED")
              << " (" << g_fail << " failures)\n";
    return g_fail == 0 ? 0 : 1;
}
