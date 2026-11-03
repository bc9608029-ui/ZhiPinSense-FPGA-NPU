// Diagnostic harness for the iCraft 3.39 same-process continuous-inference
// one-frame output delay.  Every experiment processes frames 7-18 in ONE
// process and changes exactly ONE variable at a time, so the process-/device-
// level state that holds the stale result can be localized.
//
// Experiments (selected with --experiment N):
//   0 baseline (single Session reused)
//        Device + Network created once; ONE Session reused for all 12 frames
//        (fresh input tensors per frame).  Isolates Session-reuse.
//   1 current scheme (fresh Session per frame)
//        Device + Network created once; a FRESH Session + fresh tensors per
//        frame (this is exactly npu_only_smoke.cpp).  Reproduces 2/12.
//   2 reload Network per frame
//        Device once; Network re-created from JSON + raw each frame, then a
//        fresh Session + fresh tensors.
//   3 fresh HostDevice per frame
//        Device + Network once; a fresh HostDevice::Init() per frame (official
//        API, no guessed construction); fresh Session on that device.
//   4 reopen ZG330 Device per frame
//        Network once; per frame: fresh Session + tensors (destroyed BEFORE
//        Device::Close), then Device::Close + Device::Open. No stale objects.
//   5 two independent Sessions (ping-pong)
//        Device + Network once; two Sessions pre-created; alternate per frame;
//        each output is tied to its own input frame. Last frame is read back.
//   6 log-only observation (NOT scored)
//        Reads layerCount() before/after each forward and records waitForReady
//        result + timing.  getOpWait() is NOT called (register semantics
//        unconfirmed).  No handshake/FGPA register is ever written.
//
// Forbidden here (by spec): setOpWait(), Device::reset() with unconfirmed
// level, clearMMUCache(), icoreCalc(), FPGA_STATE_CLEAR_REG, FPGA_RESET_REG,
// EXHS_ACK/VLD and any /dev/mem register write.  Frame indices are never
// offset and no frame is dropped or warmed-up.
//
// gnu++17.  Official iCraft APIs only.

#include <icraft-backends/zg330backend/zg330backend.h>
#include <icraft-backends/hostbackend/backend.h>
#include <icraft-xir/core/network.h>
#include <icraft-xrt/core/device.h>
#include <icraft-xrt/core/session.h>
#include <icraft-xrt/core/tensor.h>
#include <icraft-xrt/dev/host_device.h>
#include <icraft-xrt/dev/zg330_device.h>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

constexpr std::size_t kFrameLength = 1024;
constexpr std::size_t kPlanes = 5;
constexpr std::size_t kFrameBytes = kPlanes * kFrameLength;   // 5120
constexpr std::size_t kIqBytes = 2 * kFrameLength;            // 2048 int8
constexpr std::size_t kPhysicalBytes = 3 * kFrameLength;      // 3072 int8
constexpr float kIqScale = 1.0f / 127.0f;
constexpr float kPhysicalScale = 2.0f / 127.0f;
constexpr const char* kDeviceUrl = "axi://zg330aiu?npu=0x40000000&dma=0x80000000";
constexpr const char* kClasses[8] = {"BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"};
constexpr std::chrono::milliseconds kReadyTimeout{10000};

using ZG330Backend = icraft::xrt::zg330::ZG330Backend;
using HostBackend = icraft::xrt::HostBackend;

std::vector<char> read_binary(const std::string& path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) throw std::runtime_error("cannot open " + path);
    return {std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
}

std::vector<int64_t> shape_of(const icraft::xir::Value& value) {
    std::vector<int64_t> result;
    for (const auto dim : value.tensorType()->shape) result.push_back(dim);
    return result;
}

bool same_shape(const std::vector<int64_t>& a, std::initializer_list<int64_t> b) {
    return a == std::vector<int64_t>(b);
}

void dequantize(const char* frame, std::vector<float>& iq, std::vector<float>& physical) {
    const int8_t* iq_int8 = reinterpret_cast<const int8_t*>(frame);
    const int8_t* physical_int8 = reinterpret_cast<const int8_t*>(frame + kIqBytes);
    for (std::size_t i = 0; i < kIqBytes; ++i) iq[i] = static_cast<float>(iq_int8[i]) * kIqScale;
    for (std::size_t i = 0; i < kPhysicalBytes; ++i) physical[i] = static_cast<float>(physical_int8[i]) * kPhysicalScale;
}

icraft::xrt::Tensor make_fp32_input(const icraft::xir::Value& value, const float* source,
                                    std::size_t element_count, const icraft::xrt::MemRegion& region) {
    const auto dtype = value.tensorType();
    if (!dtype->element_dtype.getStorageType().isFP32()) {
        throw std::runtime_error("compiled input storage is not FP32");
    }
    auto tensor = icraft::xrt::Tensor(value).mallocOn(region);
    tensor.write(0, const_cast<char*>(reinterpret_cast<const char*>(source)), element_count * sizeof(float));
    return tensor;
}

std::vector<icraft::xrt::Tensor> make_inputs(const icraft::xir::Network& network,
                                             const std::vector<float>& iq,
                                             const std::vector<float>& physical,
                                             const icraft::xrt::MemRegion& region) {
    std::vector<icraft::xrt::Tensor> inputs;
    inputs.reserve(2);
    for (std::size_t i = 0; i < network.inputs().size(); ++i) {
        const auto value = network.inputs()[i];
        const auto shape = shape_of(value);
        if (same_shape(shape, {1, 2, 1024})) inputs.push_back(make_fp32_input(value, iq.data(), kIqBytes, region));
        else if (same_shape(shape, {1, 3, 1024})) inputs.push_back(make_fp32_input(value, physical.data(), kPhysicalBytes, region));
        else throw std::runtime_error("unexpected compiled input shape");
    }
    return inputs;
}

std::vector<float> read_fp32_logits(const icraft::xrt::Tensor& tensor) {
    std::vector<char> bytes(tensor.dtype().bytes());
    auto host = tensor.to(icraft::xrt::HostDevice::MemRegion());
    host.read(bytes.data(), 0, bytes.size());
    if (bytes.size() != 8 * sizeof(float)) throw std::runtime_error("unexpected logits size");
    std::vector<float> logits(8);
    std::memcpy(logits.data(), bytes.data(), bytes.size());
    return logits;
}

std::size_t argmax(const std::vector<float>& v) {
    return static_cast<std::size_t>(std::distance(v.begin(), std::max_element(v.begin(), v.end())));
}

// reference_argmax.txt: "frame_id,argmax_id,argmax_class,ood,ground_truth"
std::map<int, int> load_reference_argmax(const std::string& path) {
    std::ifstream stream(path);
    if (!stream) throw std::runtime_error("cannot open reference file " + path);
    std::map<int, int> ref;
    std::string line;
    bool header = true;
    while (std::getline(stream, line)) {
        if (line.empty()) continue;
        if (header) { header = false; continue; }
        std::stringstream ss(line);
        std::string cell;
        std::vector<std::string> cols;
        while (std::getline(ss, cell, ',')) cols.push_back(cell);
        if (cols.size() < 4) continue;
        if (cols[3] != "1") ref[std::stoi(cols[0])] = std::stoi(cols[1]);
    }
    return ref;
}

double mean(const std::vector<double>& v) {
    if (v.empty()) return 0.0;
    double s = 0.0;
    for (double x : v) s += x;
    return s / static_cast<double>(v.size());
}
double maximum(const std::vector<double>& v) {
    if (v.empty()) return 0.0;
    return *std::max_element(v.begin(), v.end());
}

struct Summary {
    int matched = 0;
    int compared = 0;
    int delay_matched = 0;
    int delay_compared = 0;
    int timeout = 0;
    int error = 0;
    std::vector<double> setup_ms;
    std::vector<double> forward_ms;
};

struct FrameOut {
    int frame_id = -1;
    bool has_logits = false;    // forward + read produced 8 logits
    bool timed_out = false;     // waitForReady returned false
    bool errored = false;       // an exception was thrown during the frame
    std::string err;            // exception message (empty unless errored)
    std::vector<float> logits;
    double setup_ms = -1.0;
    double forward_ms = -1.0;
    long layer_before = -1;     // experiment 6 only
    long layer_after = -1;
    bool has_layers = false;
};

// forward + waitForReady + read. Throws on structural errors (wrong output
// count / size). Returns timed_out=true when waitForReady timed out.
struct Fwd {
    std::vector<float> logits;
    bool timed_out;
    double ms;
};
Fwd forward_read(icraft::xrt::Session& session, const std::vector<icraft::xrt::Tensor>& inputs) {
    const auto t0 = std::chrono::steady_clock::now();
    const auto outputs = session.forward(inputs);
    if (outputs.size() != 1) throw std::runtime_error("unexpected output count");
    const bool ready = outputs[0].waitForReady(kReadyTimeout);
    const auto logits = read_fp32_logits(outputs[0]);   // may throw
    const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
    return {logits, !ready, ms};
}

// RAII guard that closes a ZG330 Device exactly once on scope exit, on every
// path (normal return, timeout, or exception).  Close failure is captured into
// *err rather than propagated out of a destructor.  Used by experiment 4 so the
// device is never left open and never closed while a Session/Tensor that
// depends on it is still alive.
struct DeviceGuard {
    icraft::xrt::Device dev;
    std::string* err;
    bool closed = false;

    DeviceGuard(icraft::xrt::Device d, std::string* e) : dev(std::move(d)), err(e) {}
    DeviceGuard(const DeviceGuard&) = delete;
    DeviceGuard& operator=(const DeviceGuard&) = delete;

    void close_now() {
        if (closed) return;
        closed = true;   // single attempt; do not retry from the destructor
        try {
            icraft::xrt::Device::Close(dev);
        } catch (const std::exception& e) {
            if (err && err->empty()) *err = std::string("Device::Close failed: ") + e.what();
        }
    }
    ~DeviceGuard() { close_now(); }
};

void emit_frame(int exp, const FrameOut& f, const std::map<int, int>& ref, Summary& s) {
    std::cout << "DIAG_FRAME exp=" << exp << " frame=" << f.frame_id;

    const bool has_ref = ref.count(f.frame_id);
    const int ref_id = has_ref ? ref.at(f.frame_id) : -1;

    if (f.errored) {
        ++s.error;
        std::cout << " pred=-1 ref=" << ref_id
                  << " result=ERROR delay=- setup=-1.000 forward=-1.000 wait=ERR rc=1"
                  << " err=" << f.err;
    } else if (f.timed_out) {
        ++s.timeout;
        const long pred = f.has_logits ? static_cast<long>(argmax(f.logits)) : -1;
        std::cout << " pred=" << pred << " ref=" << ref_id
                  << " result=TIMEOUT delay=-"
                  << " setup=" << std::fixed << std::setprecision(3) << f.setup_ms
                  << " forward=" << f.forward_ms
                  << " wait=TIMEOUT rc=1";
    } else if (!f.has_logits) {
        ++s.error;
        std::cout << " pred=-1 ref=" << ref_id
                  << " result=ERROR delay=- setup=" << std::fixed << std::setprecision(3) << f.setup_ms
                  << " forward=-1.000 wait=ERR rc=1";
    } else {
        const long pred = static_cast<long>(argmax(f.logits));
        std::string result;
        if (!has_ref) result = "NO_REF";
        else {
            ++s.compared;
            if (pred == ref_id) { ++s.matched; result = "MATCH"; }
            else result = "MISMATCH";
        }
        char delay = '-';
        if (ref.count(f.frame_id - 1)) {
            ++s.delay_compared;
            if (pred == ref.at(f.frame_id - 1)) { ++s.delay_matched; delay = 'y'; }
            else delay = 'n';
        }
        std::cout << " pred=" << pred << " ref=" << ref_id
                  << " result=" << result << " delay=" << delay
                  << " setup=" << std::fixed << std::setprecision(3) << f.setup_ms
                  << " forward=" << f.forward_ms
                  << " wait=OK rc=0";
    }

    if (f.has_layers) {
        std::cout << " layer_b=" << f.layer_before << " layer_a=" << f.layer_after;
    }
    std::cout << '\n';

    if (f.setup_ms >= 0.0) s.setup_ms.push_back(f.setup_ms);
    if (f.forward_ms >= 0.0) s.forward_ms.push_back(f.forward_ms);
}

void emit_summary(int exp, const Summary& s) {
    std::cout << "DIAG exp=" << exp
              << " match=" << s.matched << "/" << s.compared
              << " delay_shift=" << s.delay_matched << "/" << s.delay_compared
              << " timeout=" << s.timeout
              << " error=" << s.error;
    if (!s.setup_ms.empty() || !s.forward_ms.empty()) {
        std::cout << "  forward avg=" << std::fixed << std::setprecision(3) << mean(s.forward_ms)
                  << " ms max=" << maximum(s.forward_ms)
                  << " ms  setup avg=" << mean(s.setup_ms) << " ms max=" << maximum(s.setup_ms) << " ms";
    }
    std::cout << '\n';

    const bool pass = (s.matched == 12 && s.compared == 12 &&
                       s.delay_matched == 0 && s.delay_compared == 11 &&
                       s.timeout == 0 && s.error == 0);
    std::cout << (pass ? "DIAG_RESULT=PASS" : "DIAG_RESULT=FAIL") << '\n';
}

}  // namespace

int main(int argc, char** argv) {
    int experiment = 0;
    std::string model, raw, tensor, reference;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        auto next = [&](const char* name) -> std::string {
            if (i + 1 >= argc) throw std::runtime_error(std::string("missing value for ") + name);
            return argv[++i];
        };
        if (a == "--experiment") experiment = std::stoi(next("--experiment"));
        else if (a == "--model") model = next("--model");
        else if (a == "--raw") raw = next("--raw");
        else if (a == "--tensor") tensor = next("--tensor");
        else if (a == "--reference") reference = next("--reference");
        else throw std::runtime_error("unknown argument: " + a);
    }
    if (model.empty() || raw.empty() || tensor.empty()) throw std::runtime_error("--model/--raw/--tensor required");
    if (experiment < 0 || experiment > 6) throw std::runtime_error("--experiment must be 0..6");

    const auto payload = read_binary(tensor);
    if (payload.empty() || payload.size() % kFrameBytes != 0) throw std::runtime_error("bad tensor size");
    if (payload.size() / kFrameBytes < 19) throw std::runtime_error("tensor has fewer than 19 frames");
    const std::map<int, int> ref = reference.empty() ? std::map<int, int>{} : load_reference_argmax(reference);

    std::cout << "== experiment " << experiment << " ==\n";
    Summary s;

    // Per-frame body helper: dequantize, run the frame inside try/catch, emit.
    auto frame_loop = [&](auto&& run) {
        for (int f = 7; f <= 18; ++f) {
            const char* frame = payload.data() + static_cast<std::size_t>(f) * kFrameBytes;
            std::vector<float> iq(kIqBytes), phys(kPhysicalBytes);
            dequantize(frame, iq, phys);

            FrameOut out;
            out.frame_id = f;
            try {
                run(f, iq, phys, out);
            } catch (const std::exception& e) {
                out.errored = true;
                out.err = e.what();
            }
            emit_frame(experiment, out, ref, s);
        }
    };

    try {
        switch (experiment) {
        case 0: {
            // Single Session reused; Device + Network once; fresh tensors/frame.
            auto device = icraft::xrt::Device::Open(kDeviceUrl);
            auto network = icraft::xir::Network::CreateFromJsonFile(model);
            network.lazyLoadParamsFromFile(raw);
            auto session = icraft::xrt::Session::Create<ZG330Backend, HostBackend>(
                network, { device, icraft::xrt::HostDevice::Default() });
            session.apply();

            frame_loop([&](int f, const std::vector<float>& iq, const std::vector<float>& phys, FrameOut& out) {
                const auto t0 = std::chrono::steady_clock::now();
                const auto inputs = make_inputs(network, iq, phys, icraft::xrt::HostDevice::MemRegion());
                out.setup_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
                const auto r = forward_read(session, inputs);
                out.logits = r.logits; out.timed_out = r.timed_out;
                out.forward_ms = r.ms; out.has_logits = !r.logits.empty();
            });
            icraft::xrt::Device::Close(device);
            break;
        }
        case 1: {
            // Current scheme: fresh Session + fresh tensors per frame.
            auto device = icraft::xrt::Device::Open(kDeviceUrl);
            auto network = icraft::xir::Network::CreateFromJsonFile(model);
            network.lazyLoadParamsFromFile(raw);

            frame_loop([&](int f, const std::vector<float>& iq, const std::vector<float>& phys, FrameOut& out) {
                const auto t0 = std::chrono::steady_clock::now();
                auto session = icraft::xrt::Session::Create<ZG330Backend, HostBackend>(
                    network, { device, icraft::xrt::HostDevice::Default() });
                session.apply();
                const auto inputs = make_inputs(network, iq, phys, icraft::xrt::HostDevice::MemRegion());
                out.setup_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
                const auto r = forward_read(session, inputs);
                out.logits = r.logits; out.timed_out = r.timed_out;
                out.forward_ms = r.ms; out.has_logits = !r.logits.empty();
            });
            icraft::xrt::Device::Close(device);
            break;
        }
        case 2: {
            // Reload Network per frame; Device once.
            auto device = icraft::xrt::Device::Open(kDeviceUrl);

            frame_loop([&](int f, const std::vector<float>& iq, const std::vector<float>& phys, FrameOut& out) {
                const auto t0 = std::chrono::steady_clock::now();
                auto network = icraft::xir::Network::CreateFromJsonFile(model);
                network.lazyLoadParamsFromFile(raw);
                auto session = icraft::xrt::Session::Create<ZG330Backend, HostBackend>(
                    network, { device, icraft::xrt::HostDevice::Default() });
                session.apply();
                const auto inputs = make_inputs(network, iq, phys, icraft::xrt::HostDevice::MemRegion());
                out.setup_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
                const auto r = forward_read(session, inputs);
                out.logits = r.logits; out.timed_out = r.timed_out;
                out.forward_ms = r.ms; out.has_logits = !r.logits.empty();
            });
            icraft::xrt::Device::Close(device);
            break;
        }
        case 3: {
            // Fresh HostDevice::Init() per frame; Device + Network once.
            auto device = icraft::xrt::Device::Open(kDeviceUrl);
            auto network = icraft::xir::Network::CreateFromJsonFile(model);
            network.lazyLoadParamsFromFile(raw);

            frame_loop([&](int f, const std::vector<float>& iq, const std::vector<float>& phys, FrameOut& out) {
                const auto t0 = std::chrono::steady_clock::now();
                auto host_dev = icraft::xrt::HostDevice::Init();   // official fresh handle
                auto session = icraft::xrt::Session::Create<ZG330Backend, HostBackend>(
                    network, { device, host_dev });
                session.apply();
                const auto inputs = make_inputs(network, iq, phys, host_dev.defaultMemRegion());
                out.setup_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
                const auto r = forward_read(session, inputs);
                out.logits = r.logits; out.timed_out = r.timed_out;
                out.forward_ms = r.ms; out.has_logits = !r.logits.empty();
            });
            icraft::xrt::Device::Close(device);
            break;
        }
        case 4: {
            // Reopen ZG330 Device per frame; Network once. A DeviceGuard closes
            // the device on EVERY path (success / timeout / exception). Session
            // and tensors live in an inner scope so they are destroyed BEFORE
            // the device is closed; no stale object is reused, and a Close
            // failure is recorded as a frame ERROR. No Device::reset, no
            // register write.
            auto network = icraft::xir::Network::CreateFromJsonFile(model);
            network.lazyLoadParamsFromFile(raw);

            frame_loop([&](int f, const std::vector<float>& iq, const std::vector<float>& phys, FrameOut& out) {
                std::string close_err;
                DeviceGuard guard{ icraft::xrt::Device::Open(kDeviceUrl), &close_err };

                try {
                    const auto t0 = std::chrono::steady_clock::now();
                    {
                        auto session = icraft::xrt::Session::Create<ZG330Backend, HostBackend>(
                            network, { guard.dev, icraft::xrt::HostDevice::Default() });
                        session.apply();
                        const auto inputs = make_inputs(network, iq, phys, icraft::xrt::HostDevice::MemRegion());
                        out.setup_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
                        const auto r = forward_read(session, inputs);
                        out.logits = r.logits; out.timed_out = r.timed_out;
                        out.forward_ms = r.ms; out.has_logits = !r.logits.empty();
                    }   // session + inputs destroyed here, before Close
                } catch (const std::exception& e) {
                    out.errored = true;
                    out.err = e.what();
                }

                guard.close_now();   // Close on every path
                if (!close_err.empty()) {
                    out.errored = true;
                    if (out.err.empty()) out.err = close_err;
                    else out.err += " | " + close_err;
                }
            });
            break;
        }
        case 5: {
            // Two pre-built, independent Sessions alternated strictly SERIALLY
            // (ping-pong). Odd frames -> sess_a, even -> sess_b. Only ONE
            // forward is ever in flight: forward_read() calls forward(), then
            // waitForReady(), then reads + copies the logits, all before the
            // next frame is submitted. No multi-threading, no result offset, no
            // dropped/warm-up frame; the last frame (18) is read and compared
            // like every other.
            auto device = icraft::xrt::Device::Open(kDeviceUrl);
            auto network = icraft::xir::Network::CreateFromJsonFile(model);
            network.lazyLoadParamsFromFile(raw);
            auto sess_a = icraft::xrt::Session::Create<ZG330Backend, HostBackend>(
                network, { device, icraft::xrt::HostDevice::Default() });
            sess_a.apply();
            auto sess_b = icraft::xrt::Session::Create<ZG330Backend, HostBackend>(
                network, { device, icraft::xrt::HostDevice::Default() });
            sess_b.apply();

            frame_loop([&](int f, const std::vector<float>& iq, const std::vector<float>& phys, FrameOut& out) {
                auto& session = ((f % 2) == 0) ? sess_b : sess_a;
                const auto t0 = std::chrono::steady_clock::now();
                const auto inputs = make_inputs(network, iq, phys, icraft::xrt::HostDevice::MemRegion());
                out.setup_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
                const auto r = forward_read(session, inputs);   // forward -> wait -> read, fully serial
                out.logits = r.logits; out.timed_out = r.timed_out;
                out.forward_ms = r.ms; out.has_logits = !r.logits.empty();
            });
            icraft::xrt::Device::Close(device);
            break;
        }
        case 6: {
            // Log-only observation: layerCount() before/after each forward.
            // No handshake/FGPA register is written; getOpWait() is NOT read.
            auto device = icraft::xrt::Device::Open(kDeviceUrl);
            auto zg = device.cast<icraft::xrt::ZG330Device>();
            auto network = icraft::xir::Network::CreateFromJsonFile(model);
            network.lazyLoadParamsFromFile(raw);

            frame_loop([&](int f, const std::vector<float>& iq, const std::vector<float>& phys, FrameOut& out) {
                const auto layer_before = static_cast<long>(zg.layerCount());
                const auto t0 = std::chrono::steady_clock::now();
                auto session = icraft::xrt::Session::Create<ZG330Backend, HostBackend>(
                    network, { device, icraft::xrt::HostDevice::Default() });
                session.apply();
                const auto inputs = make_inputs(network, iq, phys, icraft::xrt::HostDevice::MemRegion());
                out.setup_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
                const auto r = forward_read(session, inputs);
                const auto layer_after = static_cast<long>(zg.layerCount());
                out.logits = r.logits; out.timed_out = r.timed_out;
                out.forward_ms = r.ms; out.has_logits = !r.logits.empty();
                out.layer_before = layer_before; out.layer_after = layer_after;
                out.has_layers = true;
            });
            icraft::xrt::Device::Close(device);
            break;
        }
        }

        emit_summary(experiment, s);
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "DIAG_SETUP_ERROR exp=" << experiment << ": " << e.what() << '\n';
        return 1;
    }
}
