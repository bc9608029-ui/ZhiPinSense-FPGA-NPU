// Smart-scan software/fpga/auto backend driver (header-only, C++11).
//
// Implements the frozen backend enumeration (SHARED_CONTRACT_PARALLEL_20261029.md
// §1) and the anti-tear PSD readback protocol (contract/pspl_register_map.md §4).
//
//   - Backend::software : never touches the FPGA; the caller's software FFT.
//   - Backend::fpga     : FPGA scan only; any fault surfaces as an error.
//   - Backend::auto     : try FPGA first; ANY fault (version mismatch, protocol
//                         error, overflow, frame not committed, read timeout,
//                         DDR error, sample-count mismatch) falls back to the
//                         software FFT.  Stale FPGA results are never returned.
//
// The register I/O is abstracted behind RegIo so the same driver runs against
// the board's mmap-ed User_Reg_ channel or a host-side mock (see the TB /
// selftest).  The concrete mmap base address is platform-specific and is wired
// at board bring-up, not hardcoded here.
#ifndef RML24_FPGA_BACKEND_HPP
#define RML24_FPGA_BACKEND_HPP

#include <cstdint>
#include <cstring>
#include <vector>
#include <array>
#include <functional>

namespace rml24 {

enum class Backend { software = 0, fpga = 1, auto_ = 2 };

enum class ScanError {
    ok = 0,
    bad_config,          // IQ base not 64B-aligned or byte count not 4096-multiple
    version_mismatch,    // SS_VERSION != 8'h01
    start_timeout,       // done never asserted
    ddr_error,           // SS_ERR_CODE bit1
    fft_protocol_error,  // SS_ERR_CODE bit2
    fft_overflow,        // SS_ERR_CODE bit3
    sample_count_mismatch,// SS_ERR_CODE bit4
    frame_not_committed, // committed_valid == 0
    generation_changed,  // frame_id/bank changed during readback (anti-tear)
    read_timeout         // rd_ready never asserted during PSD readback
};

inline const char* scan_error_name(ScanError e) {
    switch (e) {
        case ScanError::ok:                   return "ok";
        case ScanError::bad_config:           return "bad_config";
        case ScanError::version_mismatch:     return "version_mismatch";
        case ScanError::start_timeout:        return "start_timeout";
        case ScanError::ddr_error:            return "ddr_error";
        case ScanError::fft_protocol_error:   return "fft_protocol_error";
        case ScanError::fft_overflow:         return "fft_overflow";
        case ScanError::sample_count_mismatch:return "sample_count_mismatch";
        case ScanError::frame_not_committed:  return "frame_not_committed";
        case ScanError::generation_changed:   return "generation_changed";
        case ScanError::read_timeout:         return "read_timeout";
    }
    return "unknown";
}

// Frozen register map (byte offsets into the User_Reg_ channel).
static constexpr std::uint32_t SS_IQ_BASE     = 0x00000u;
static constexpr std::uint32_t SS_IQ_BYTES    = 0x00004u;
static constexpr std::uint32_t SS_CTRL        = 0x00008u;
static constexpr std::uint32_t SS_VERSION     = 0x0000Cu;
static constexpr std::uint32_t SS_STATUS      = 0x00010u;
static constexpr std::uint32_t SS_FRAME_ID    = 0x00014u;
static constexpr std::uint32_t SS_IQ_ACCEPTED = 0x00018u;
static constexpr std::uint32_t SS_ERR_CODE    = 0x0001Cu;
static constexpr std::uint32_t SS_RD_CTRL     = 0x00020u;
static constexpr std::uint32_t SS_RD_DATA_LO  = 0x00024u;
static constexpr std::uint32_t SS_RD_DATA_HI  = 0x00028u;

static constexpr std::uint8_t  SCAN_VERSION       = 0x01u;  // frozen §2
static constexpr std::uint32_t FFT_LENGTH         = 1024u;
static constexpr std::uint32_t FRAME_BYTES        = 4096u;  // 1024 samples x 4 B

static constexpr std::uint32_t CTRL_START         = 0x1u;
static constexpr std::uint32_t CTRL_CLEAR         = 0x2u;

static constexpr std::uint32_t ST_BUSY            = 0x01u;
static constexpr std::uint32_t ST_DONE            = 0x02u;
static constexpr std::uint32_t ST_ERROR           = 0x04u;
static constexpr std::uint32_t ST_COMMITTED_VALID = 0x08u;
static constexpr std::uint32_t ST_COMMITTED_BANK  = 0x10u;
static constexpr std::uint32_t ST_PROTOCOL_ERROR  = 0x20u;
static constexpr std::uint32_t ST_OVERFLOW        = 0x40u;
static constexpr std::uint32_t ST_RD_READY        = 0x80u;

static constexpr std::uint32_t EC_BAD_CONFIG          = 0x01u;
static constexpr std::uint32_t EC_DDR_ERROR           = 0x02u;
static constexpr std::uint32_t EC_FFT_PROTOCOL_ERROR  = 0x04u;
static constexpr std::uint32_t EC_FFT_OVERFLOW        = 0x08u;
static constexpr std::uint32_t EC_SAMPLE_COUNT_MISMATCH = 0x10u;

// Abstract 32-bit register channel (board mmap, or a host mock).
class RegIo {
public:
    virtual ~RegIo() {}
    virtual std::uint32_t read32(std::uint32_t offset) = 0;
    virtual void write32(std::uint32_t offset, std::uint32_t value) = 0;
};

// A software PSD: takes interleaved int16 I/Q and returns FFT_LENGTH 64-bit
// power words in fftshift order (the same storage order the FPGA double buffer
// uses), so the CPU-side noise-floor/threshold/bin-merge stages are identical
// for both backends.
using SoftwarePsdFn =
    std::function<std::vector<std::uint64_t>(const std::vector<std::array<std::int16_t, 2>>& iq)>;

struct ScanResult {
    Backend backend_used = Backend::auto_;
    bool ok = false;
    ScanError error = ScanError::ok;
    std::vector<std::uint64_t> psd;   // 1024 x 64-bit (54-bit power, high 10 bits zero)
    std::uint32_t frame_id = 0;
    std::uint32_t accepted_samples = 0;
};

// Reads one 64-bit PSD word through SS_RD_CTRL/SS_RD_DATA_LO/HI with a
// rd_ready timeout.  Returns false on timeout.
inline bool psd_read_word(RegIo& io, std::uint32_t bank, std::uint32_t addr,
                          std::uint64_t& out, std::uint32_t poll_limit) {
    io.write32(SS_RD_CTRL, ((bank & 1u) << 10) | (addr & 0x3FFu));
    std::uint32_t polls = 0;
    while (polls++ < poll_limit) {
        if (io.read32(SS_STATUS) & ST_RD_READY) {
            std::uint64_t lo = io.read32(SS_RD_DATA_LO);
            std::uint64_t hi = io.read32(SS_RD_DATA_HI);
            out = (hi << 32) | lo;
            return true;
        }
    }
    return false;
}

// FPGA scan.  Writes config, starts the job, waits for completion, classifies
// errors, then reads the committed bank with the anti-tear generation recheck.
// Returns ok=false with a classified ScanError on any fault; never a partial
// "stale" frame.
inline bool fpga_scan(RegIo& io,
                      std::uint32_t iq_base_addr,
                      std::uint32_t iq_byte_count,
                      ScanResult& result,
                      std::uint32_t start_poll_limit = 2000000u,
                      std::uint32_t rd_poll_limit = 100000u,
                      unsigned readback_retries = 3u) {
    result.backend_used = Backend::fpga;
    result.psd.clear();
    result.ok = false;
    result.error = ScanError::ok;

    const std::uint32_t ver = io.read32(SS_VERSION) & 0xFFu;
    if (ver != SCAN_VERSION) { result.error = ScanError::version_mismatch; return false; }

    io.write32(SS_CTRL, CTRL_CLEAR);

    io.write32(SS_IQ_BASE, iq_base_addr);
    io.write32(SS_IQ_BYTES, iq_byte_count);

    io.write32(SS_CTRL, CTRL_START);

    std::uint32_t polls = 0;
    std::uint32_t status = 0;
    while (polls++ < start_poll_limit) {
        status = io.read32(SS_STATUS);
        if (status & ST_DONE) break;
    }
    if (!(status & ST_DONE)) { result.error = ScanError::start_timeout; return false; }

    const std::uint32_t err_code = io.read32(SS_ERR_CODE);
    result.accepted_samples = io.read32(SS_IQ_ACCEPTED);
    result.frame_id = io.read32(SS_FRAME_ID);

    if (err_code & EC_BAD_CONFIG)           { result.error = ScanError::bad_config;            return false; }
    if (err_code & EC_DDR_ERROR)            { result.error = ScanError::ddr_error;             return false; }
    if (err_code & EC_FFT_PROTOCOL_ERROR)   { result.error = ScanError::fft_protocol_error;    return false; }
    if (err_code & EC_FFT_OVERFLOW)         { result.error = ScanError::fft_overflow;          return false; }
    if (err_code & EC_SAMPLE_COUNT_MISMATCH){ result.error = ScanError::sample_count_mismatch; return false; }

    for (unsigned attempt = 0; attempt < readback_retries; ++attempt) {
        status = io.read32(SS_STATUS);
        if (!(status & ST_COMMITTED_VALID)) { result.error = ScanError::frame_not_committed; return false; }
        if (status & (ST_PROTOCOL_ERROR | ST_OVERFLOW)) {
            result.error = (status & ST_OVERFLOW) ? ScanError::fft_overflow
                                                  : ScanError::fft_protocol_error;
            return false;
        }
        const std::uint32_t bank = (status & ST_COMMITTED_BANK) ? 1u : 0u;
        const std::uint32_t frame_before = io.read32(SS_FRAME_ID);

        std::vector<std::uint64_t> psd;
        psd.reserve(FFT_LENGTH);
        bool read_ok = true;
        for (std::uint32_t a = 0; a < FFT_LENGTH; ++a) {
            std::uint64_t word = 0;
            if (!psd_read_word(io, bank, a, word, rd_poll_limit)) { read_ok = false; break; }
            psd.push_back(word);
        }

        const std::uint32_t frame_after = io.read32(SS_FRAME_ID);
        const std::uint32_t status_after = io.read32(SS_STATUS);
        const std::uint32_t bank_after = (status_after & ST_COMMITTED_BANK) ? 1u : 0u;

        if (!read_ok) { result.error = ScanError::read_timeout; return false; }
        if (frame_after != frame_before || bank_after != bank) {
            // A new frame committed mid-read: the word we read may be torn.
            // Retry the whole frame; a lone committed_bank check cannot
            // protect against the next round's overwrite (contract §5).
            continue;
        }
        result.psd = std::move(psd);
        result.frame_id = frame_after;
        result.ok = true;
        result.error = ScanError::ok;
        return true;
    }
    result.error = ScanError::generation_changed;
    return false;
}

// Backend::auto: try FPGA, fall back to software FFT on ANY fault.
inline ScanResult auto_scan(RegIo& io,
                            std::uint32_t iq_base_addr,
                            std::uint32_t iq_byte_count,
                            const std::vector<std::array<std::int16_t, 2>>& iq,
                            const SoftwarePsdFn& software_psd) {
    ScanResult r;
    if (fpga_scan(io, iq_base_addr, iq_byte_count, r)) {
        r.backend_used = Backend::fpga;
        return r;
    }
    // Fall back; never return the FPGA's stale partial result.
    r.backend_used = Backend::software;
    r.psd = software_psd(iq);
    r.ok = !r.psd.empty();
    if (!r.ok) r.error = ScanError::sample_count_mismatch;  // software could not run
    else        r.error = ScanError::ok;
    return r;
}

}  // namespace rml24

#endif  // RML24_FPGA_BACKEND_HPP
