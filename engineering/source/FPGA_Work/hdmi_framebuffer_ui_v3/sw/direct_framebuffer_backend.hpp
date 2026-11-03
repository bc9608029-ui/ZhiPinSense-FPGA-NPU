// direct_framebuffer_backend.hpp — common safe HDMI display backend (FMQL30TAI).
//
// This is the ONLY place that touches /dev/udmabuf0 and /dev/mem for the HDMI
// framebuffer.  It replaces the iCraft `Device::Open("axi://zg330aiu?npu=...")`
// + `getMemRegion("udma")` + `defaultRegRegion()` path, which hangs the board's
// Linux when the NPU is not instantiated in the HDMI-only bitstream.
//
//   - physical address / capacity are read from
//       /sys/class/u-dma-buf/udmabuf0/{phys_addr,size}   (never hard-coded)
//   - the framebuffer is written ONLY through submit(): a regular-RAM staging
//     buffer is copied to the device mapping with scalar 16-bit stores
//     (never NEON/SIMD wide stores — see scalar_copy16).
//   - frame_ctrl is accessed by mmap()ing a single 4 KiB page of /dev/mem
//   - registers are written ONLY after the version gate passes, and every
//     register write is read back and verified
//   - msync() is attempted; EINVAL is tolerated (u-dma-buf does not support it),
//     and /sys/class/u-dma-buf/udmabuf0/sync_for_device is used to push the
//     framebuffer to the device.  The success/unsupported messages are printed
//     ONCE, never per frame.
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

    int frame_width               = 1280;
    int frame_height              = 720;

    // The v3 bitstream is a double-buffer (ping-pong) design: two frames, back
    // buffer rendered while the PL reads the front buffer.
    int num_frames                = 2;

    std::uint64_t frame_bytes() const {
        return static_cast<std::uint64_t>(frame_width) * frame_height * 2; // RGB565
    }
    std::size_t frame_pixels() const {
        return static_cast<std::size_t>(frame_width) * frame_height;
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

// Scalar 16-bit device copy: copies npix RGB565 words from a regular-RAM staging
// buffer into a device mapping.  `dst` is volatile so the compiler emits a single
// 16-bit store per element and never vectorizes into NEON/SIMD wide stores — the
// u-dma-buf device mapping rejects those with SIGBUS.  This is the ONLY function
// allowed to write the framebuffer.  Marked to keep the auto-vectorizer off.
void scalar_copy16(volatile std::uint16_t* dst,
                   const std::uint16_t* src,
                   std::size_t npix);

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
    std::size_t frame_pixels() const { return cfg_.frame_pixels(); }
    int num_frames() const           { return cfg_.num_frames; }

    // Copy a full frame from a regular-RAM staging buffer (frame_pixels() words)
    // into device frame `frame_index` using scalar 16-bit stores.  Validates the
    // pointer and frame index and never writes outside the mapped two-frame range.
    // Returns false (FAIL print) on any invalid input.
    bool submit(const std::uint16_t* src, int frame_index);

    // Volatile view of a device frame (read-only use in host tests).  Valid only
    // after init()==true.
    volatile std::uint16_t* frame_buffer(int frame_index);

    // Read a frame_ctrl register by byte offset.
    std::uint32_t read_reg(std::uint32_t offset) const;
    // Write a frame_ctrl register by byte offset, then read back and verify.
    // Prints FAIL and returns false on mismatch.
    bool write_reg(std::uint32_t offset, std::uint32_t value);

    // Push the framebuffer to the device: msync (EINVAL tolerated) + sync_for_device.
    // The success/unsupported notice is printed ONCE; real errors print every time.
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

    volatile std::uint16_t* fb_ = nullptr;     // fb_map_ as volatile RGB565 words
    volatile std::uint32_t* mem_ = nullptr;    // mem_map_ as 32-bit registers

    bool ready_ = false;
    bool sync_logged_ = false;                 // success/unsupported notice, once
};

} // namespace dfb
