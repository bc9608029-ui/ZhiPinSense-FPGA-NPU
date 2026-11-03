// libiio_gate.cpp -- the pre-SDR libiio build gate (Task 39e5b / Task 3).
//
// Build both configurations (see build_libiio_gate.sh):
//   * SDR_ADAPTER_HAVE_LIBIIO=0  -> mock backend (offline; proves the no-libiio
//                                   path still builds and runs).
//   * SDR_ADAPTER_HAVE_LIBIIO=1  -> real libiio backend, linked against libiio.
//       With no ADALM-Pluto attached it must fail FAST and CLEARLY with
//       "device not found" (exit 2) -- never crash, hang, or fall back to MOCK.
//
// Exit codes: 0 = opened + read OK, 2 = device not found / open failed,
//             1 = usage or other error.
//
// This gate does NOT claim real acquisition: the libiio read path is only
// exercised when a device is actually present (待 Pluto 到货后非盲复测).

#include "pluto.hpp"

#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>

namespace {

void usage(const char* argv0) {
    std::fprintf(stderr,
                 "usage: %s [--uri <libiio-uri>] [--frames N]\n"
                 "  exit 0 = opened+read OK, 2 = device not found, 1 = other\n",
                 argv0);
}

}  // namespace

int main(int argc, char** argv) {
    pluto::Config cfg;
    int frames = 4;

    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a == "--uri" && i + 1 < argc) {
            cfg.uri = argv[++i];
        } else if (a == "--frames" && i + 1 < argc) {
            frames = std::atoi(argv[++i]);
        } else if (a == "-h" || a == "--help") {
            usage(argv[0]);
            return 1;
        } else {
            std::fprintf(stderr, "unknown arg: %s\n", argv[i]);
            return 1;
        }
    }

#if defined(SDR_ADAPTER_HAVE_LIBIIO)
    // ---- libiio build: real backend, must fail fast without a device. ------
    std::unique_ptr<iio::Backend> backend;
    try {
        backend.reset(pluto::make_backend(cfg));
    } catch (const std::exception& e) {
        // No Pluto present -> fail fast and clearly (never fall back to MOCK).
        std::fprintf(stderr, "GATE: %s\n", e.what());
        return 2;
    }

    std::printf("GATE: libiio backend opened (device present)\n");
    pluto::PlutoIqSource src(cfg, *backend);
    iq::Frame f;
    int got = 0;
    for (int k = 0; k < frames && src.next(f); ++k) {
        ++got;
    }
    std::printf("GATE: read %d frame(s)\n", got);
    return 0;
#else
    // ---- offline mock build: prove the framing path with a driven mock. ----
    iio::MockBackend mock;
    // The mock ring starts empty; a real producer advances it.  Drive enough
    // samples for `frames` full frames (plus a little) so no stall occurs.
    mock.advance(static_cast<std::uint64_t>(iq::kComplexSamplesPerFrame) *
                     static_cast<std::uint64_t>(frames) +
                 64);

    pluto::PlutoIqSource src(cfg, mock);
    iq::Frame f;
    int got = 0;
    for (int k = 0; k < frames && src.next(f); ++k) {
        ++got;
    }
    std::printf("GATE: mock backend (offline, no libiio), read %d frame(s)\n", got);
    return 0;
#endif
}
