// test_gate10_sequential.cpp -- host test for the Gate 10 twelve-class sequential
// self-test (task 39e5 Task A).  Gate 10 synthesises and classifies all twelve
// classes IN ONE PROCESS, so the per-class waveform build must be deterministic,
// class-distinct, and free of cross-class state bleed; a malformed --seed (A4) must
// fail closed.  This test proves those properties on the host, before any board run,
// using the exact same code the board runs (sdr::build_tx_waveform + sdr::crc32_i16)
// and the exact same CLI parser (board::opt_u64).
//
// Covered:
//   A4  --seed=0x39e50001 hex parse (and decimal / rejection fail-closed);
//   A1  the per-class waveform identity (tx_waveform_crc32) is deterministic and
//        unique, so the board log's per-class CRC can tell two classes apart;
//   A3  building class N does not depend on class N-1 (no shared generator state),
//        which is what lets all 12 run in a single process;
//   the waveform is finite, peak-limited, and interleaved (even length) for every
//        class.
//
// Build/run: see host_tests/build_host_tests.sh (links resampler.cpp).

#include "../board_package/board_common.hpp"
#include "../sdr_adapter/rf_waveform_12class.hpp"
#include "../sdr_adapter/crc32.hpp"

#include <cstdio>
#include <cstdint>
#include <set>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;
void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

// A stable argv built from string tokens (argv[0] is the program name).
struct Cli {
    std::vector<std::string> storage;
    std::vector<char*> argv;
    explicit Cli(const std::vector<std::string>& args) : storage(args) {
        argv.reserve(storage.size());
        for (auto& s : storage) argv.push_back(const_cast<char*>(s.c_str()));
    }
    int argc() const { return static_cast<int>(argv.size()); }
    char** ptr() { return argv.data(); }
};

std::uint32_t build_crc(int cls, std::uint64_t seed) {
    std::vector<std::int16_t> iq;
    double peak = 0.0, rms = 0.0;
    sdr::build_tx_waveform(cls, seed, /*frames=*/4, /*peak_limit=*/1638.0,
                           iq, &peak, &rms);
    return sdr::crc32_i16(iq);
}

void test_seed_parse() {
    Cli hex({"prog", "--seed=0x39e50001"});
    check(board::opt_u64(hex.argc(), hex.ptr(), "--seed", 0) == 0x39e50001ULL,
          "A4: --seed=0x39e50001 parses as hex");

    Cli dec({"prog", "--seed=100"});
    check(board::opt_u64(dec.argc(), dec.ptr(), "--seed", 0) == 100ULL,
          "--seed=100 decimal");

    Cli oct({"prog", "--seed", "0123"});
    check(board::opt_u64(oct.argc(), oct.ptr(), "--seed", 0) == 123ULL,
          "0123 stays decimal (not octal)");

    Cli cap({"prog", "--seed=0X39e5"});
    check(board::opt_u64(cap.argc(), cap.ptr(), "--seed", 0) == 0x39e5ULL,
          "0X (capital) hex prefix accepted");

    bool threw = false;
    try {
        Cli neg({"prog", "--seed=-1"});
        (void)board::opt_u64(neg.argc(), neg.ptr(), "--seed", 0);
    } catch (const std::exception&) { threw = true; }
    check(threw, "negative seed rejected (no silent wrap)");

    threw = false;
    try {
        Cli bare({"prog", "--seed=0x"});
        (void)board::opt_u64(bare.argc(), bare.ptr(), "--seed", 0);
    } catch (const std::exception&) { threw = true; }
    check(threw, "bare 0x seed rejected");

    threw = false;
    try {
        Cli junk({"prog", "--seed=12zz"});
        (void)board::opt_u64(junk.argc(), junk.ptr(), "--seed", 0);
    } catch (const std::exception&) { threw = true; }
    check(threw, "trailing junk seed rejected");
}

void test_sequential_12class() {
    const std::uint64_t seed = 0x39e50001ULL;
    std::vector<std::uint32_t> crcs;
    std::set<std::uint32_t> unique;

    for (int c = 0; c < 12; ++c) {
        std::vector<std::int16_t> iq;
        double peak = 0.0, rms = 0.0;
        sdr::build_tx_waveform(c, seed, /*frames=*/4, /*peak_limit=*/1638.0,
                               iq, &peak, &rms);
        const std::uint32_t crc = sdr::crc32_i16(iq);
        crcs.push_back(crc);
        unique.insert(crc);

        char what[128];
        std::snprintf(what, sizeof(what), "class %d waveform finite/interleaved", c);
        bool ok = !iq.empty() && (iq.size() % 2 == 0) && peak > 0.0 && rms > 0.0;
        double mx = 0.0;
        for (std::size_t k = 0; k < iq.size() / 2; ++k) {
            const int a = std::abs(static_cast<int>(iq[k * 2 + 0]));
            const int b = std::abs(static_cast<int>(iq[k * 2 + 1]));
            mx = mx > a ? mx : a;
            mx = mx > b ? mx : b;
        }
        ok = ok && mx <= 1639.0;
        check(ok, what);

        std::snprintf(what, sizeof(what), "class %d deterministic (rebuild == same CRC)", c);
        check(build_crc(c, seed) == crc, what);
    }

    check(unique.size() == 12, "12 classes -> 12 distinct waveform CRCs");
    check(crcs.size() == 12, "built all 12 classes");

    // Cross-class independence: the CRC of class c is identical whether it is built
    // in isolation or immediately after class c-1 in the same process.
    for (int c = 1; c < 12; ++c) {
        // build in the same order Gate 10 does: ... c-1 then c ...
        std::vector<std::int16_t> iq;
        double peak = 0.0, rms = 0.0;
        sdr::build_tx_waveform(c - 1, seed, 4, 1638.0, iq, &peak, &rms);   // class c-1
        sdr::build_tx_waveform(c, seed, 4, 1638.0, iq, &peak, &rms);       // then c
        char what[128];
        std::snprintf(what, sizeof(what), "class %d CRC independent of class %d before it", c, c - 1);
        check(sdr::crc32_i16(iq) == crcs[static_cast<std::size_t>(c)], what);
    }
}

}  // namespace

int main() {
    std::printf("test_gate10_sequential\n");
    test_seed_parse();
    test_sequential_12class();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
