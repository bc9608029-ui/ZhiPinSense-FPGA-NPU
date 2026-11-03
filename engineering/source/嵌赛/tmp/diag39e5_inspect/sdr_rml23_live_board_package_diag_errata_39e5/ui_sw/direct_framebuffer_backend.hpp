// direct_framebuffer_backend.hpp — common safe HDMI display backend (FMQL30TAI).
//
// This is the ONLY place that touches /dev/udmabuf0 and /dev/mem for the HDMI
// framebuffer.  It replaces the iCraft `Device::Open("axi://zg330aiu?npu=...")`
// + `getMemRegion("udma")` + `defaultRegRegion()` path, which hangs the board's
// Linux when the NPU is not instantiated in the HDMI-only bitstream.
//
//   - physical address / capacity are read from
//       /sys/class/u-dma-buf/udmabuf0/{phys_addr,size}   (never hard-coded)
//   - framebuffer is written by mmap()ing /dev/udmabuf0 (RGB565)
//   - frame_ctrl is accessed by mmap()ing a single 4 KiB page of /dev/mem
//   - registers are written ONLY after the version gate passes, and every
//     register write is read back and verified
//   - msync() is attempted; EINVAL is tolerated (u-dma-buf does not support it),
//     and /sys/class/u-dma-buf/udmabuf0/sync_for_device is used to push the
//     framebuffer to the device
//
// It NEVER touches the NPU, DMA/NPU base addresses, Flash, or Device::Open.
// Every failure prints a clear FAIL line; callers exit non-zero.
//
// All paths and constants live in `Config`, and every OS side effect goes through
// the `Io` interface, so the logic can be exercised on a host with a mock (see
// test_direct_framebuffer_backend.cpp).

#pragma once

#include <cstdint>
#include <cstddef>
#include <string>
#include <vector>

// submit_frame() writes the u-dma-buf mapping one 16-bit scalar store at a time.
// `volatile` alone already forbids GCC from auto-vectorizing those stores, but
// the function is ALSO pinned down (defense in depth, for the AArch64 objdump
// audit): noinline + no-tree-vectorize + no-tree-slp-vectorize.
#if defined(__GNUC__)
#define DFB_SCALAR_STORE_ONLY \
    __attribute__((noinline, optimize("no-tree-vectorize", "no-tree-slp-vectorize")))
#else
#define DFB_SCALAR_STORE_ONLY
#endif

namespace dfb {

// ---- injectable configuration (host mock tests override these) ------------
struct Config {
    std::string udmabuf_dev      = "/dev/udmabuf0";
    std::string sysfs_base       = "/sys/class/u-dma-buf/udmabuf0/";
    std::string mem_dev          = "/dev/mem";
    std::string sync_node        = "/sys/class/u-dma-buf/udmabuf0/sync_for_device";

    std::uint64_t frame_ctrl_base = 0x40080000ULL;   // frame_ctrl AXI-Lite base
    std::uint32_t version_offset  = 0x0CU;           // slv_reg3  = version
    std::uint32_t wr_addr_offset  = 0x50U;           // slv_reg20 = buffer select (bit0)
    std::uint32_t rd_addr_offset  = 0x54U;           // slv_reg21 = framebuffer base >> 3
    std::uint32_t expected_version = 0x20230218U;

    // Diagnostic READ-ONLY offsets (task 39e5 Task B, B4 vsync/vblank audit).
    // These are only ever read by --display-diagnostic; never written by software.
    // The 720p timing is a fixed constant in the RTL; reading the timing config
    // confirms the display block is configured, but there is NO confirmed
    // vblank-status register to poll for a userspace flip-sync, so the ping-pong
    // flip stays "latched at frame start by frame_fifo_read" (see
    // docs/CDC_FALSE_PATH_EXCEPTION_AUDIT.md).
    std::uint32_t disable_hdmi_offset = 0x78U;       // slv_reg30 = disable_hdmi (bit0, reset 0)
    std::uint32_t h_sync_offset       = 0x94U;       // slv_reg37 = H_SYNC
    std::uint32_t v_sync_offset       = 0xA4U;       // slv_reg41 = V_SYNC
    std::uint32_t vtc_enable_offset   = 0xB4U;       // slv_reg45 = vtc_enable

    int frame_width               = 1280;
    int frame_height              = 720;

    // The v3 bitstream is a double-buffer (ping-pong) design: two frames, back
    // buffer rendered while the PL reads the front buffer.
    int num_frames                = 2;

    std::uint64_t frame_bytes() const {
        return static_cast<std::uint64_t>(frame_width) * frame_height * 2; // RGB565
    }
    std::uint64_t total_bytes() const {
        return frame_bytes() * static_cast<std::uint64_t>(num_frames);
    }
};

// ---- pure logic (host-testable, no device I/O) ----------------------------

// Parse an unsigned integer in C++ style: hex (0x..), decimal, or octal,
// with optional surrounding whitespace.  Returns false on malformed input.
bool parse_u64(const std::string& text, std::uint64_t* out);

struct CheckResult { bool ok = false; std::string why; };

// Single-framebuffer gate: 8-byte aligned, under 1 GiB (fb>>3 fits the 27-bit
// camera_rd_addr), and fits the given udmabuf capacity.
CheckResult check_framebuffer(std::uint64_t phys,
                              std::uint64_t capacity,
                              std::uint64_t frame_bytes);

// Two-buffer (ping-pong) gate: fb1 = fb0 + frame_bytes; both 8-byte aligned,
// both under 1 GiB, pair fits capacity.  On success writes fb1 to *fb1 (if given).
CheckResult check_double_buffer(std::uint64_t fb0,
                                std::uint64_t frame_bytes,
                                std::uint64_t capacity,
                                std::uint64_t* fb1);

// Version gate: registers may be written only when the register matches expected.
bool version_allows_write(std::uint32_t version, std::uint32_t expected);

// Register round-trip gate: true only when the read-back equals what was written.
bool readback_matches(std::uint32_t written, std::uint32_t readback);

// msync() outcome classification.  rc==0 -> ok; rc<0 with errno==EINVAL is
// tolerated (u-dma-buf does not implement msync); anything else fails.
enum class MsyncAction { Continue, TolerateEinval, Fail };
MsyncAction classify_msync(int rc, int err);

// ---- OS side effects (replaceable for host mock tests) --------------------
class Io {
public:
    virtual ~Io() = default;

    // Read the whole file as text.  Throws std::runtime_error on I/O failure.
    virtual std::string read_text(const std::string& path) = 0;

    // Open a device; returns fd >= 0, or -1 (errno available via last_errno()).
    virtual int open_dev(const std::string& path, int flags) = 0;

    // mmap PROT_READ|WRITE, MAP_SHARED.  Returns MAP_FAILED on error.
    virtual void* map(int fd, std::size_t length, std::uint64_t offset) = 0;
    virtual int unmap(void* addr, std::size_t length) = 0;
    virtual int close_fd(int fd) = 0;

    // msync; returns 0 on success, -1 on error (errno via last_errno()).
    virtual int msync_range(void* addr, std::size_t length, int flags) = 0;

    // Write "1" to the sync_for_device node; returns true if it was writable.
    virtual bool write_sync_node(const std::string& path) = 0;

    virtual int last_errno() const = 0;
};

// ---- real OS backend (the board) ------------------------------------------
class RealIo : public Io {
public:
    std::string read_text(const std::string& path) override;
    int open_dev(const std::string& path, int flags) override;
    void* map(int fd, std::size_t length, std::uint64_t offset) override;
    int unmap(void* addr, std::size_t length) override;
    int close_fd(int fd) override;
    int msync_range(void* addr, std::size_t length, int flags) override;
    bool write_sync_node(const std::string& path) override;
    int last_errno() const override;

private:
    int errno_ = 0;
};

// ---- the safe framebuffer backend -----------------------------------------
class DirectFramebufferBackend {
public:
    DirectFramebufferBackend(const Config& cfg, Io& io);
    ~DirectFramebufferBackend();   // RAII: munmap + close

    DirectFramebufferBackend(const DirectFramebufferBackend&) = delete;
    DirectFramebufferBackend& operator=(const DirectFramebufferBackend&) = delete;

    // Resolve phys/capacity from sysfs, validate, map /dev/udmabuf0 and /dev/mem,
    // verify the version.  On any failure prints FAIL and returns false.  No
    // register is ever written unless the version gate passes.
    bool init();

    std::uint64_t phys_addr() const { return phys_; }
    std::uint64_t capacity() const  { return capacity_; }
    bool ready() const              { return ready_; }

    // Ordinary-memory staging framebuffer (one frame of RGB565 words, heap RAM).
    // Phase programs render into this buffer — vectorization is harmless here
    // because it is ordinary memory.  They must NOT obtain a pointer to the
    // device mmap; the only device write path is submit_frame() below.
    std::uint16_t* staging();

    // Present one fully-rendered frame to the PL, strictly in this order:
    //   1. validate frame_index (0..num_frames-1) and pixel_count (1..frame_words)
    //   2. copy pixel_count RGB565 words from staging_data into frame[frame_index]
    //      using SCALAR volatile 16-bit stores only (no NEON/SIMD wide stores)
    //   3. sync_for_device (msync, EINVAL tolerated; driver sync node)
    //   4. flip the PL read select to frame_index (read-back verified)
    // The flip happens only after copy + sync complete, so the PL never reads a
    // half-written frame.  Returns false (with a FAIL line) if any step fails.
    DFB_SCALAR_STORE_ONLY
    bool submit_frame(int frame_index,
                      const std::uint16_t* staging_data,
                      std::size_t pixel_count);

    // [M18-0 Tool B] Copy + sync a frame WITHOUT flipping the PL read select.
    // Identical to submit_frame except it never writes wr_addr, so the PL stays
    // latched on whichever buffer it currently selects -- this is the
    // "single-buffer lock, fully disable flip" diagnostic path.  Purely additive:
    // submit_frame() and every production path are unchanged.
    DFB_SCALAR_STORE_ONLY
    bool submit_frame_no_flip(int frame_index,
                              const std::uint16_t* staging_data,
                              std::size_t pixel_count);

    // [M18-0 Tool D] Read one frame's RGB565 words out of the device mapping into
    // an ordinary buffer, for pre/post-submit CRC verification.  READ-ONLY: this
    // never writes the mapping; the only device write paths remain submit_frame /
    // submit_frame_no_flip / clear_frame / clear_all_frames.  Returns false on an
    // out-of-range frame_index or word count, or before a successful init.
    bool read_frame_words(int frame_index, std::uint16_t* dst, std::size_t words) const;

    // Clear one frame (RGB565 black = 0x0000) in the device mapping using scalar
    // 16-bit stores only (same SIGBUS discipline as submit_frame), then flush.
    // Used at startup so the PL never reads uninitialised DDR (task 39e5 Task B).
    DFB_SCALAR_STORE_ONLY
    bool clear_frame(int frame_index);

    // Clear all num_frames frames, then a single flush.  Must complete BEFORE the
    // framebuffer base (rd_addr) is programmed, so the PL first reads black frames
    // rather than whatever was left in DDR after the bitstream reload.
    bool clear_all_frames();

    // Blank / un-blank the HDMI output (M17 Task F startup-stripes fix).  Writes
    // disable_hdmi (slv_reg30 bit0); the RTL 2-FF-syncs it into display_en, so
    // enable=false blanks and enable=true un-blanks.  Because display_en is 1 at
    // reset, the PL scans the reset rd_addr (0x7E00000) as garbage in the gap
    // between bitstream load and software rd_addr programming -- blanking first
    // and un-blanking only after frame 0 is valid + rd_addr programmed closes that
    // gap.  Returns false (with a FAIL line) on a read-back mismatch.  Must only
    // be called after a successful init().
    bool set_display_enable(bool enable);

    // Read a frame_ctrl register by byte offset.
    std::uint32_t read_reg(std::uint32_t offset) const;
    // Write a frame_ctrl register by byte offset, then read back and verify.
    // Prints FAIL and returns false on mismatch.
    bool write_reg(std::uint32_t offset, std::uint32_t value);

    // Push the framebuffer to the device: msync (EINVAL tolerated) + sync_for_device.
    // Returns false (FAIL print) only on a non-EINVAL msync error.
    bool flush();

private:
    void fail(const std::string& msg) const;   // prints "[DFB] FAIL: ..."
    void info(const std::string& msg) const;   // prints "[DFB] ..."

    const Config cfg_;
    Io& io_;

    int fb_fd_ = -1;
    void* fb_map_ = nullptr;
    std::size_t fb_len_ = 0;

    int mem_fd_ = -1;
    void* mem_map_ = nullptr;
    std::size_t mem_len_ = 0;

    std::uint64_t phys_ = 0;
    std::uint64_t capacity_ = 0;

    volatile std::uint16_t* fb_ = nullptr;     // fb_map_ as RGB565 words (device mmap)
    volatile std::uint32_t* mem_ = nullptr;    // mem_map_ as 32-bit registers

    std::vector<std::uint16_t> stage_;         // one frame of ordinary heap memory

    std::size_t frame_words() const {
        return static_cast<std::size_t>(cfg_.frame_bytes() / 2);
    }

    bool sync_logged_ = false;   // heartbeat errata: msync/sync_for_device info once
    bool ready_ = false;
};

} // namespace dfb
