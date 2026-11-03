// Offline File-IQ end-to-end demo (host or board; iCraft-free, no SDR).
//
// Runs the full offline chain and emits one JSON-lines verdict per frame:
//
//   FileIqSource -> 1024-sample int16 frame -> deployment preprocessing
//   (physical frontend) -> MockClassifier (MOCK logits) -> ResultFrame
//   -> stdout JSONL (and an optional Unix socket).
//
// Usage:
//   offline_e2e [--iq <file>] [--frames N] [--socket <path>]
//
//   --iq     replay this interleaved int16 IQ file (frame_count * 4096 bytes);
//            when omitted, a deterministic synthetic file is generated and
//            replayed through FileIqSource so the chain is self-contained.
//   --frames number of 1024-sample frames to run (0 = until end-of-file).
//   --socket optional Unix domain socket path for the HDMI/UI adapter.
//
// NOTE: classification is MOCK (every result carries "mock":true).  This is NOT
// real inference and must never be reported as such.

#include "categories.hpp"
#include "classify.hpp"
#include "iq_source.hpp"
#include "offline_chain.hpp"
#include "ui_report.hpp"
#include "unix_socket_sink.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

namespace {

// Fan-out sink: forwards each line to several sinks (stdout + optional socket).
struct FanoutSink : ui::Sink {
    std::vector<ui::Sink*> sinks;
    void write(const std::string& line) override {
        for (ui::Sink* s : sinks) s->write(line);
    }
};

// Write `nframes` deterministic frames (via SyntheticIqSource) to `path` so the
// chain can start from a real file without any external IQ asset.
void write_synthetic_file(const std::string& path, std::uint64_t nframes) {
    SyntheticIqSource gen(nframes, /*loop=*/false);
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    if (!out) {
        std::fprintf(stderr, "offline_e2e: cannot create %s\n", path.c_str());
        std::exit(2);
    }
    iq::Frame f;
    while (gen.next(f)) {
        out.write(reinterpret_cast<const char*>(f.iq),
                  static_cast<std::streamsize>(iq::kFrameBytes));
    }
}

}  // namespace

int main(int argc, char** argv) {
    std::string iq_path;
    std::string socket_path;
    std::uint64_t max_frames = 0;

    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        auto next = [&]() -> std::string {
            if (i + 1 >= argc) return "";
            return argv[++i];
        };
        if (a == "--iq") iq_path = next();
        else if (a == "--frames") max_frames = std::strtoull(next().c_str(), nullptr, 10);
        else if (a == "--socket") socket_path = next();
        else {
            std::fprintf(stderr, "offline_e2e: unknown arg '%s'\n", a.c_str());
            return 2;
        }
    }

    // Build the source from a file (generating a deterministic one if needed).
    std::string tmp;
    std::uint64_t frame_count = 0;
    if (iq_path.empty()) {
        tmp = "offline_e2e_synth_iq.bin";
        frame_count = max_frames ? max_frames : 16;
        write_synthetic_file(tmp, frame_count);
        iq_path = tmp;
        std::fprintf(stderr, "offline_e2e: generated %llu synthetic frames -> %s\n",
                     static_cast<unsigned long long>(frame_count), tmp.c_str());
    }

    std::ifstream in(iq_path, std::ios::binary);
    if (!in) {
        std::fprintf(stderr, "offline_e2e: cannot open %s\n", iq_path.c_str());
        return 2;
    }
    in.seekg(0, std::ios::end);
    const std::streamoff bytes = in.tellg();
    in.seekg(0, std::ios::beg);
    if (bytes <= 0 || bytes % static_cast<std::streamoff>(iq::kFrameBytes) != 0) {
        std::fprintf(stderr, "offline_e2e: IQ file size not a multiple of %zu bytes\n",
                     iq::kFrameBytes);
        return 2;
    }
    frame_count = static_cast<std::uint64_t>(bytes) / iq::kFrameBytes;
    std::vector<char> buf(static_cast<std::size_t>(bytes));
    in.read(buf.data(), bytes);

    FileIqSource src(buf, frame_count, /*loop=*/false);
    classify::MockClassifier cls(cat::current_10());

    ui::StdoutSink out_sink;
    std::unique_ptr<ui::UnixSocketSink> sock;
    if (!socket_path.empty()) {
        sock.reset(new ui::UnixSocketSink(socket_path));
        std::fprintf(stderr, "offline_e2e: also writing to Unix socket %s\n",
                     socket_path.c_str());
    }

    FanoutSink sink;
    sink.sinks.push_back(&out_sink);
    if (sock) sink.sinks.push_back(sock.get());

    chain::ChainConfig cfg;
    cfg.max_frames = max_frames;
    chain::ChainStats st = chain::run(src, cls, cat::current_10(), sink, nullptr, cfg);

    std::fprintf(stderr,
                 "offline_e2e: frames=%llu classified=%llu short=%llu "
                 "overflow=%llu dropped=%llu discontinuity=%llu\n",
                 static_cast<unsigned long long>(st.frames),
                 static_cast<unsigned long long>(st.classified),
                 static_cast<unsigned long long>(st.short_frames),
                 static_cast<unsigned long long>(st.overflow),
                 static_cast<unsigned long long>(st.dropped),
                 static_cast<unsigned long long>(st.discontinuity));

    if (sock) std::fprintf(stderr, "offline_e2e: socket write errors=%zu\n",
                           sock->error_count());

    if (!tmp.empty()) std::remove(tmp.c_str());
    return 0;
}
