// Host selftest for software/fpga/auto backend driver logic (no hardware).
//
// Exercises fpga_backend.hpp against a mock RegIo to prove the frozen `auto`
// contract: any fault (version mismatch / bad config / timeout / overflow /
// frame-not-committed / generation change / sample-count mismatch) forces a
// software fallback and never returns a stale FPGA result.
//
// Build (any C++11 compiler):
//   g++ -std=c++11 -Wall -Wextra -I. selftest_fpga_backend.cpp -o selftest_fpga_backend
#include "fpga_backend.hpp"

#include <cstdio>
#include <cstdlib>
#include <vector>
#include <array>
#include <cstdint>

using namespace rml24;

namespace {

// Mock of the SS_ register channel.  Behaves like the engine described in
// contract/pspl_register_map.md, with injectable fault modes.
class MockRegIo : public RegIo {
public:
    std::uint8_t version = SCAN_VERSION;
    bool fail_timeout = false;      // never assert done
    bool fail_generation = false;   // frame_id advances mid-readback
    std::uint32_t force_err_code = 0; // OR-ed into completion err code
    bool fail_not_committed = false; // never assert committed_valid

    std::uint32_t iq_base = 0, iq_bytes = 0;
    std::uint32_t status = 0, frame_id = 0, err_code = 0, iq_accepted = 0;
    std::uint64_t rd_data = 0;
    bool rd_ready = false;
    unsigned rd_ctrl_writes = 0;

    std::uint32_t read32(std::uint32_t off) override {
        switch (off) {
            case SS_VERSION:     return version;
            case SS_STATUS:      return status | (rd_ready ? ST_RD_READY : 0);
            case SS_FRAME_ID:    return frame_id;
            case SS_IQ_ACCEPTED: return iq_accepted;
            case SS_ERR_CODE:    return err_code;
            case SS_RD_DATA_LO:  return static_cast<std::uint32_t>(rd_data & 0xFFFFFFFFull);
            case SS_RD_DATA_HI:  return static_cast<std::uint32_t>(rd_data >> 32);
            default:             return 0xFFFFFFFFu;
        }
    }

    void write32(std::uint32_t off, std::uint32_t v) override {
        switch (off) {
            case SS_IQ_BASE:  iq_base = v; break;
            case SS_IQ_BYTES: iq_bytes = v; break;
            case SS_RD_CTRL: {
                rd_ready = true;
                ++rd_ctrl_writes;
                const std::uint32_t bank = (v >> 10) & 1u;
                const std::uint32_t addr = v & 0x3FFu;
                // A simple deterministic PSD word so readback is checkable.
                rd_data = (static_cast<std::uint64_t>(addr) << 16) | bank;
                // Fault injection: a new frame commits every 100 read requests
                // (several times per 1024-bin pass), so the driver's anti-tear
                // retry can never observe a stable frame and must exhaust its
                // 3 retries and fall back to software.
                if (fail_generation && rd_ctrl_writes % 100 == 0) {
                    ++frame_id;
                    status = (status & ~ST_COMMITTED_BANK) | (~frame_id & 1u ? ST_COMMITTED_BANK : 0);
                }
                break;
            }
            case SS_CTRL: {
                if (v & CTRL_CLEAR) {
                    status &= ~(ST_DONE | ST_ERROR);
                    err_code = 0;
                }
                if (v & CTRL_START) {
                    const bool bad = (iq_base & 0x3Fu) != 0 || (iq_bytes % FRAME_BYTES) != 0 || iq_bytes == 0;
                    if (bad) {
                        status = ST_DONE | ST_ERROR;
                        err_code = EC_BAD_CONFIG;
                        return;
                    }
                    if (fail_timeout) { status = ST_BUSY; return; }
                    // Normal completion.
                    frame_id = iq_bytes / FRAME_BYTES;
                    iq_accepted = iq_bytes / 4;
                    err_code = force_err_code;
                    status = ST_DONE | ST_COMMITTED_VALID
                           | ((~frame_id & 1u) ? ST_COMMITTED_BANK : 0)
                           | (err_code ? ST_ERROR : 0);
                    if (fail_not_committed) status &= ~ST_COMMITTED_VALID;
                    if (err_code & EC_FFT_OVERFLOW) status |= ST_OVERFLOW;
                    if (err_code & EC_FFT_PROTOCOL_ERROR) status |= ST_PROTOCOL_ERROR;
                }
                break;
            }
            default: break;
        }
    }
};

int failures = 0;
void check(bool cond, const char* what) {
    if (!cond) { std::printf("SELFTEST FAIL: %s\n", what); ++failures; }
    else       { std::printf("SELFTEST PASS: %s\n", what); }
}

// Software fallback: a distinctive PSD (single bin 7 = 42) so the test can
// prove the fallback actually ran.
std::vector<std::uint64_t> software_psd(const std::vector<std::array<std::int16_t, 2>>&) {
    std::vector<std::uint64_t> p(FFT_LENGTH, 0);
    p[7] = 42;
    return p;
}

}  // namespace

int main() {
    std::vector<std::array<std::int16_t, 2>> iq;  // not read by the mock path

    // 1. happy path -> fpga backend, no fallback.
    {
        MockRegIo io;
        ScanResult r = auto_scan(io, 0, FRAME_BYTES, iq, software_psd);
        check(r.backend_used == Backend::fpga && r.ok, "auto happy path uses fpga");
    }

    // 2. version mismatch -> software fallback.
    {
        MockRegIo io; io.version = 0x02;
        ScanResult r = auto_scan(io, 0, FRAME_BYTES, iq, software_psd);
        check(r.backend_used == Backend::software && r.ok && r.psd[7] == 42,
              "version mismatch falls back to software");
    }

    // 3. bad config -> software fallback.
    {
        MockRegIo io;
        ScanResult r = auto_scan(io, 4, FRAME_BYTES, iq, software_psd);  // base not 64B-aligned
        check(r.backend_used == Backend::software && r.ok, "bad config falls back");
    }

    // 4. start timeout -> software fallback.
    {
        MockRegIo io; io.fail_timeout = true;
        ScanResult r = auto_scan(io, 0, FRAME_BYTES, iq, software_psd);
        check(r.backend_used == Backend::software && r.ok, "timeout falls back");
    }

    // 5. overflow -> software fallback.
    {
        MockRegIo io; io.force_err_code = EC_FFT_OVERFLOW;
        ScanResult r = auto_scan(io, 0, FRAME_BYTES, iq, software_psd);
        check(r.backend_used == Backend::software && r.ok, "overflow falls back");
    }

    // 6. frame not committed -> software fallback.
    {
        MockRegIo io; io.fail_not_committed = true;
        ScanResult r = auto_scan(io, 0, FRAME_BYTES, iq, software_psd);
        check(r.backend_used == Backend::software && r.ok, "frame-not-committed falls back");
    }

    // 7. generation change mid-readback -> software fallback (no stale PSD).
    {
        MockRegIo io; io.fail_generation = true;
        ScanResult r = auto_scan(io, 0, FRAME_BYTES, iq, software_psd);
        check(r.backend_used == Backend::software && r.ok,
              "generation change falls back (no stale fpga result)");
    }

    // 8. sample-count mismatch -> software fallback.
    {
        MockRegIo io; io.force_err_code = EC_SAMPLE_COUNT_MISMATCH;
        ScanResult r = auto_scan(io, 0, FRAME_BYTES, iq, software_psd);
        check(r.backend_used == Backend::software && r.ok, "sample-count mismatch falls back");
    }

    std::printf("SELFTEST_FPGA_BACKEND %s failures=%d\n",
                failures == 0 ? "PASS" : "FAIL", failures);
    return failures == 0 ? 0 : 1;
}
