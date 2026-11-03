// direct_framebuffer_backend.cpp — implementation of the safe HDMI backend.
//
// See the header for the contract.  This file is the single choke point for
// /dev/udmabuf0 and /dev/mem access; the phase programs never touch them directly.
// The UI renders into a regular-RAM staging buffer and calls submit() to push the
// frame to the device with scalar 16-bit stores (never NEON/SIMD wide stores).

#include "direct_framebuffer_backend.hpp"

#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>

namespace dfb {

// ---- pure logic -----------------------------------------------------------

bool parse_u64(const std::string& text, std::uint64_t* out) {
    if (!out) return false;
    const std::string s = [&] {
        std::string t = text;
        std::size_t b = t.find_first_not_of(" \t\r\n");
        if (b == std::string::npos) return std::string();
        std::size_t e = t.find_last_not_of(" \t\r\n");
        return t.substr(b, e - b + 1);
    }();
    if (s.empty()) return false;

    errno = 0;
    char* end = nullptr;
    unsigned long long v = std::strtoull(s.c_str(), &end, /*base=*/0);
    if (end == s.c_str() || *end != '\0' || errno != 0) return false;
    *out = static_cast<std::uint64_t>(v);
    return true;
}

CheckResult check_framebuffer(std::uint64_t phys,
                              std::uint64_t capacity,
                              std::uint64_t frame_bytes) {
    CheckResult r;
    if (frame_bytes == 0)                  { r.why = "frame_bytes is zero"; return r; }
    if ((phys & 0x7U) != 0)                { r.why = "physical address not 8-byte aligned"; return r; }
    if (phys >= (1ULL << 30))              { r.why = "physical address >= 1 GiB (fb>>3 exceeds 27-bit addr)"; return r; }
    if (capacity < frame_bytes)            { r.why = "udmabuf capacity < one frame"; return r; }
    r.ok = true;
    return r;
}

CheckResult check_double_buffer(std::uint64_t fb0,
                                std::uint64_t frame_bytes,
                                std::uint64_t capacity,
                                std::uint64_t* fb1) {
    CheckResult r;
    if (frame_bytes == 0)                  { r.why = "frame_bytes is zero"; return r; }
    const std::uint64_t fb1v = fb0 + frame_bytes;
    if (fb1) *fb1 = fb1v;
    if ((fb0 & 0x7U) != 0)                 { r.why = "FB0 not 8-byte aligned"; return r; }
    if ((fb1v & 0x7U) != 0)                { r.why = "FB1 not 8-byte aligned"; return r; }
    if (fb0 >= (1ULL << 30))               { r.why = "FB0 >= 1 GiB"; return r; }
    if (fb1v >= (1ULL << 30))              { r.why = "FB1 >= 1 GiB"; return r; }
    if (capacity < 2 * frame_bytes)        { r.why = "udmabuf capacity < 2 frames"; return r; }
    r.ok = true;
    return r;
}

bool version_allows_write(std::uint32_t version, std::uint32_t expected) {
    return version == expected;
}

bool readback_matches(std::uint32_t written, std::uint32_t readback) {
    return written == readback;
}

MsyncAction classify_msync(int rc, int err) {
    if (rc == 0) return MsyncAction::Continue;
    if (err == EINVAL) return MsyncAction::TolerateEinval;
    return MsyncAction::Fail;
}

// ---------------------------------------------------------------------------
// scalar_copy16 — the ONLY function that writes the device framebuffer.
//
// `dst` is volatile: the C/C++ abstract machine requires each volatile store to
// be emitted exactly once, in order, so no conforming compiler (GCC or Clang)
// will widen these into NEON/SIMD stores.  The function attribute below is a
// belt-and-suspenders request to the GCC auto-vectorizer; the volatile pointer is
// the actual guarantee and is verified in the report via `objdump` / `-fopt-info`.
#if defined(__GNUC__) && !defined(__clang__)
__attribute__((noinline, optimize("no-tree-vectorize")))
#endif
void scalar_copy16(volatile std::uint16_t* dst,
                   const std::uint16_t* src,
                   std::size_t npix) {
    for (std::size_t i = 0; i < npix; ++i) {
        dst[i] = src[i];      // one scalar 16-bit store per element
    }
}

// ---- RealIo ---------------------------------------------------------------

std::string RealIo::read_text(const std::string& path) {
    std::ifstream f(path.c_str());
    if (!f.is_open()) throw std::runtime_error("cannot open " + path);
    std::ostringstream ss;
    ss << f.rdbuf();
    return ss.str();
}

int RealIo::open_dev(const std::string& path, int flags) {
    const int fd = ::open(path.c_str(), flags);
    errno_ = errno;
    return fd;
}

void* RealIo::map(int fd, std::size_t length, std::uint64_t offset) {
    void* p = ::mmap(nullptr, length, PROT_READ | PROT_WRITE, MAP_SHARED,
                     fd, static_cast<off_t>(offset));
    errno_ = errno;
    return p;
}

int RealIo::unmap(void* addr, std::size_t length) {
    const int r = ::munmap(addr, length);
    errno_ = errno;
    return r;
}

int RealIo::close_fd(int fd) {
    const int r = ::close(fd);
    errno_ = errno;
    return r;
}

int RealIo::msync_range(void* addr, std::size_t length, int flags) {
    const int r = ::msync(addr, length, flags);
    errno_ = errno;
    return r;
}

bool RealIo::write_sync_node(const std::string& path) {
    std::ofstream o(path.c_str());
    if (!o) return false;
    o << "1";
    o.flush();
    return static_cast<bool>(o);
}

int RealIo::last_errno() const { return errno_; }

// ---- DirectFramebufferBackend ---------------------------------------------

DirectFramebufferBackend::DirectFramebufferBackend(const Config& cfg, Io& io)
    : cfg_(cfg), io_(io) {}

DirectFramebufferBackend::~DirectFramebufferBackend() {
    if (mem_map_) io_.unmap(mem_map_, mem_len_);
    if (fb_map_)  io_.unmap(fb_map_, fb_len_);
    if (mem_fd_ >= 0) io_.close_fd(mem_fd_);
    if (fb_fd_ >= 0)  io_.close_fd(fb_fd_);
}

void DirectFramebufferBackend::fail(const std::string& msg) const {
    std::cerr << "[DFB] FAIL: " << msg << "\n";
}

void DirectFramebufferBackend::info(const std::string& msg) const {
    std::cout << "[DFB] " << msg << "\n";
}

bool DirectFramebufferBackend::init() {
    // 1. Resolve the true physical address and capacity from sysfs (no hardcode).
    std::uint64_t phys = 0, capacity = 0;
    try {
        const std::string phys_text = io_.read_text(cfg_.sysfs_base + "phys_addr");
        const std::string size_text = io_.read_text(cfg_.sysfs_base + "size");
        if (!parse_u64(phys_text, &phys)) {
            fail("cannot parse phys_addr '" + phys_text + "'");
            return false;
        }
        if (!parse_u64(size_text, &capacity)) {
            fail("cannot parse size '" + size_text + "'");
            return false;
        }
    } catch (const std::exception& e) {
        fail(std::string("reading udmabuf sysfs: ") + e.what());
        return false;
    }
    phys_ = phys;
    capacity_ = capacity;

    {
        std::ostringstream os;
        os << "udmabuf phys=0x" << std::hex << phys_ << std::dec
           << " size=" << capacity_
           << " frame_bytes=" << cfg_.frame_bytes()
           << " total=" << cfg_.total_bytes();
        info(os.str());
    }

    // 2. Validate before touching any device.
    CheckResult c = check_double_buffer(phys_, cfg_.frame_bytes(), capacity_, nullptr);
    if (!c.ok) { fail(c.why); return false; }

    // 3. Map the framebuffer (RGB565) from /dev/udmabuf0.
    fb_fd_ = io_.open_dev(cfg_.udmabuf_dev, O_RDWR | O_SYNC);
    if (fb_fd_ < 0) {
        fail(std::string("open ") + cfg_.udmabuf_dev + ": " + std::strerror(io_.last_errno()));
        return false;
    }
    fb_len_ = static_cast<std::size_t>(cfg_.total_bytes());
    fb_map_ = io_.map(fb_fd_, fb_len_, 0);
    if (fb_map_ == MAP_FAILED) {
        fail(std::string("mmap ") + cfg_.udmabuf_dev + ": " + std::strerror(io_.last_errno()));
        fb_map_ = nullptr;
        return false;
    }
    fb_ = static_cast<volatile std::uint16_t*>(fb_map_);

    // 4. Map the frame_ctrl register page from /dev/mem (4 KiB only).
    mem_fd_ = io_.open_dev(cfg_.mem_dev, O_RDWR | O_SYNC);
    if (mem_fd_ < 0) {
        fail(std::string("open ") + cfg_.mem_dev + ": " + std::strerror(io_.last_errno()));
        return false;
    }
    mem_len_ = 0x1000;   // one 4 KiB page, enough for frame_ctrl
    mem_map_ = io_.map(mem_fd_, mem_len_, cfg_.frame_ctrl_base);
    if (mem_map_ == MAP_FAILED) {
        fail(std::string("mmap ") + cfg_.mem_dev + ": " + std::strerror(io_.last_errno()));
        mem_map_ = nullptr;
        return false;
    }
    mem_ = static_cast<volatile std::uint32_t*>(mem_map_);

    // 5. Version gate: refuse any register write unless the version matches.
    const std::uint32_t version = read_reg(cfg_.version_offset);
    std::cout << "[DFB] frame_ctrl version = 0x" << std::hex << std::setw(8)
              << std::setfill('0') << version << std::dec
              << " (expect 0x" << std::hex << cfg_.expected_version << std::dec << ")\n";
    if (!version_allows_write(version, cfg_.expected_version)) {
        fail("version mismatch; register write refused");
        return false;
    }

    ready_ = true;
    return true;
}

volatile std::uint16_t* DirectFramebufferBackend::frame_buffer(int frame_index) {
    if (!ready_ || !fb_) return nullptr;
    if (frame_index < 0 || frame_index >= cfg_.num_frames) return nullptr;
    return fb_ + static_cast<std::size_t>(frame_index) * cfg_.frame_pixels();
}

bool DirectFramebufferBackend::submit(const std::uint16_t* src, int frame_index) {
    if (!ready_ || !fb_) {
        fail("submit before successful init");
        return false;
    }
    if (src == nullptr) {
        fail("submit: null staging buffer");
        return false;
    }
    if (frame_index < 0 || frame_index >= cfg_.num_frames) {
        fail("submit: frame index out of range");
        return false;
    }
    volatile std::uint16_t* dst = frame_buffer(frame_index);
    scalar_copy16(dst, src, cfg_.frame_pixels());
    return true;
}

std::uint32_t DirectFramebufferBackend::read_reg(std::uint32_t offset) const {
    if (!mem_) return 0;
    return mem_[offset / 4];
}

bool DirectFramebufferBackend::write_reg(std::uint32_t offset, std::uint32_t value) {
    if (!ready_ || !mem_) {
        fail("write_reg before successful init");
        return false;
    }
    mem_[offset / 4] = value;
    __sync_synchronize();
    const std::uint32_t readback = mem_[offset / 4];
    if (!readback_matches(value, readback)) {
        std::ostringstream os;
        os << "register read-back mismatch @0x" << std::hex << offset
           << ": wrote 0x" << value << " read 0x" << readback << std::dec;
        fail(os.str());
        return false;
    }
    return true;
}

bool DirectFramebufferBackend::flush() {
    if (!ready_ || !fb_map_) {
        fail("flush before successful init");
        return false;
    }
    const int rc = io_.msync_range(fb_map_, fb_len_, MS_SYNC);
    const MsyncAction action = classify_msync(rc, io_.last_errno());
    if (action == MsyncAction::Fail) {
        fail(std::string("msync udmabuf0: ") + std::strerror(io_.last_errno()));
        return false;
    }

    const bool sync_written = io_.write_sync_node(cfg_.sync_node);

    // Success/unsupported notice is printed ONCE, never per frame.
    if (!sync_logged_) {
        if (action == MsyncAction::Continue) {
            info("msync ok");
        } else {
            info("msync unsupported (EINVAL) by udmabuf0; using driver sync node");
        }
        if (sync_written) info("sync_for_device requested");
        else              info("sync_for_device node absent; framebuffer written via O_SYNC mapping");
        sync_logged_ = true;
    }
    return true;
}

} // namespace dfb
