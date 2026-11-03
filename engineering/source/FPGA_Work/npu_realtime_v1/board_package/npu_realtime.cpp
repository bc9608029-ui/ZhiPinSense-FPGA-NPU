// Persistent-Device continuous NPU inference for the ZG330 (iCraft 3.39).
//
// This program solves the same-process one-frame-delay / stale-output problem
// that forced the correctness baseline (fpga_npu_joint_v1) to reopen the
// ZG330 Device every frame (~265 ms of setup each frame).
//
// Root cause (audited against the iCraft 3.39 headers and device docs):
//   Session::forward() is ASYNC for the ZG330 backend: it returns an output
//   tensor whose "ready" is a cached software flag (TensorNode::ready_,
//   default true) gated by a hardware check function (TensorNode::check_func_).
//   Tensor::waitForReady() short-circuits when ready_==true and only polls
//   check_func_ otherwise.  The ZG330 completion check polls an FPGA state /
//   layer counter that is MONOTONIC per Device and is only re-armed by Device
//   Open (init) or Device::reset.  On a persistent Device every forward after
//   the first sees a stale "already done" completion state, waitForReady()
//   returns immediately, and the previous frame's output is read back.
//
// This program keeps Device open ONCE and re-arms the completion state before
// each frame using ONLY documented official APIs:
//   * Device::reset(level) -- level 1 = "reset FPGA state only" (documented in
//     axizg330aiu and socketzg330aiu device docs).
//   * Tensor::setReady(bool) -- re-arm the software ready cache (tensor.h).
// A --rearm sweep isolates each mechanism so the board run can pick the exact
// one that reaches a clean persistent-Device PASS.
//
// Forbidden here (by spec): private FPGA registers (STATE_CLEAR / STATE /
// EXHS_VLD / EXHS_ACK / RESET), setOpWait()/getOpWait(), clearMMUCache(),
// icoreCalc(), Device::reset() with an unconfirmed level, any /dev/mem write,
// fake sleep, and dropping/shifting/warming-up frames.  layerCount() is read
// ONLY (observation), never written.
//
// gnu++17.  Official icraft-xrt / icraft-xir / ZG330Backend / HostBackend APIs.

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
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr std::size_t kFrameLength = 1024;
constexpr std::size_t kPlanes = 5;
constexpr std::size_t kFrameBytes = kPlanes * kFrameLength;   // 5120 B SInt8 per frame
constexpr std::size_t kIqBytes = 2 * kFrameLength;            // 2048 int8 (I,Q)
constexpr std::size_t kPhysicalBytes = 3 * kFrameLength;      // 3072 int8 (power,lag1_re,lag1_im)
constexpr float kIqScale = 1.0f / 127.0f;
constexpr float kPhysicalScale = 2.0f / 127.0f;
constexpr const char* kDeviceUrl = "axi://zg330aiu?npu=0x40000000&dma=0x80000000";
constexpr const char* kClasses[8] = {"BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"};
constexpr std::chrono::milliseconds kReadyTimeout{10000};
constexpr int kCycleFirst = 7;   // validated frame range for the sequence test
constexpr int kCycleLast = 18;
constexpr int kAltFrameA = 7;    // BPSK (argmax 0) -- clearly different from B
constexpr int kAltFrameB = 10;   // QPSK (argmax 1)
constexpr double kLogitTol = 1e-3;   // full-logits "is stale" threshold

using ZG330Backend = icraft::xrt::zg330::ZG330Backend;
using HostBackend = icraft::xrt::HostBackend;

enum class Rearm { None, SetReady, Reset1, Reset1Apply, Reopen };

Rearm parse_rearm(const std::string& s) {
    if (s == "none") return Rearm::None;
    if (s == "setready") return Rearm::SetReady;
    if (s == "reset1") return Rearm::Reset1;
    if (s == "reset1_apply") return Rearm::Reset1Apply;
    if (s == "reopen") return Rearm::Reopen;
    throw std::runtime_error("unknown --rearm value: " + s);
}
const char* rearm_name(Rearm r) {
    switch (r) {
        case Rearm::None: return "none";
        case Rearm::SetReady: return "setready";
        case Rearm::Reset1: return "reset1";
        case Rearm::Reset1Apply: return "reset1_apply";
        case Rearm::Reopen: return "reopen";
    }
    return "?";
}

struct Options {
    std::string model, raw, tensor, reference;
    std::string rearm = "none";
    std::string test = "sequence";   // "sequence" | "alternating"
    int frames = 12;                 // total frames for the sequence test
    int alt_iterations = 24;         // alternating iterations (7/10 pairs)
    int rounds = 1;
};

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

double max_abs_diff(const std::vector<float>& a, const std::vector<float>& b) {
    double m = 0.0;
    const std::size_t n = std::min(a.size(), b.size());
    for (std::size_t i = 0; i < n; ++i) m = std::max(m, std::fabs(static_cast<double>(a[i]) - static_cast<double>(b[i])));
    return m;
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

// RAII guard that closes a Device exactly once on every path.  Close failure is
// captured into *err (never thrown from the destructor).  Used by the "reopen"
// control so a per-frame Device is never left open, and never closed while a
// Session/Tensor that depends on it is still alive.
struct DeviceGuard {
    icraft::xrt::Device dev;
    std::string* err;
    bool closed = false;
    DeviceGuard(icraft::xrt::Device d, std::string* e) : dev(std::move(d)), err(e) {}
    DeviceGuard(const DeviceGuard&) = delete;
    DeviceGuard& operator=(const DeviceGuard&) = delete;
    void close_now() {
        if (closed) return;
        closed = true;
        try { icraft::xrt::Device::Close(dev); }
        catch (const std::exception& e) {
            if (err && err->empty()) *err = std::string("Device::Close failed: ") + e.what();
        }
    }
    ~DeviceGuard() { close_now(); }
};

struct FrameOut {
    int frame_id = -1;
    bool has_logits = false;
    bool timed_out = false;
    bool errored = false;
    std::string err;
    std::vector<float> logits;
    double setup_ms = -1.0;
    double forward_ms = -1.0;
    long layer_before = -1;
    long layer_after = -1;
    bool has_layers = false;
};

// One forward+wait+read on an ALREADY-OPEN persistent Session/Device.
// `rearm` selects the completion re-arm applied around this frame; `is_first`
// is true for the first frame in this session's run (no stale state yet).
FrameOut forward_read_persistent(icraft::xrt::Session& session,
                                 icraft::xrt::Device& device,
                                 const icraft::xrt::ZG330Device& zg,
                                 const std::vector<icraft::xrt::Tensor>& inputs,
                                 int frame_id,
                                 Rearm rearm,
                                 bool is_first,
                                 bool record_layers) {
    FrameOut out;
    out.frame_id = frame_id;

    // Re-arm the FPGA completion state BETWEEN frames.  The first frame of the
    // session runs on the freshly-initialized hardware (no stale state).
    if (!is_first) {
        if (rearm == Rearm::Reset1) {
            device.reset(1);   // documented: "reset FPGA state only"
        } else if (rearm == Rearm::Reset1Apply) {
            device.reset(1);
            session.apply();   // re-deploy in case reset(1) cleared applied state
        }
    }

    if (record_layers) out.layer_before = static_cast<long>(zg.layerCount());

    const auto t0 = std::chrono::steady_clock::now();
    auto outputs = session.forward(inputs);
    if (outputs.size() != 1) throw std::runtime_error("unexpected output count");

    // Software re-arm of the ready cache before the wait (documented API).
    // setReady() is non-const, hence `outputs` is non-const here.
    if (rearm == Rearm::SetReady) outputs[0].setReady(false);

    const bool ready = outputs[0].waitForReady(kReadyTimeout);
    const auto logits = read_fp32_logits(outputs[0]);   // may throw
    out.forward_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();

    if (record_layers) out.layer_after = static_cast<long>(zg.layerCount());

    out.logits = logits;
    out.has_logits = !logits.empty();
    out.timed_out = !ready;
    out.has_layers = record_layers;
    return out;
}

// Control path: a FRESH Device (and Session) per frame.  This is the known
// 12/12 correctness baseline (Device reopen resets the hardware completion
// state).  Used to compare against the persistent-Device re-arm variants.
FrameOut forward_read_reopen(const icraft::xir::Network& network,
                             const char* frame_bytes,
                             int frame_id) {
    std::vector<float> iq(kIqBytes), phys(kPhysicalBytes);
    dequantize(frame_bytes, iq, phys);

    FrameOut out;
    out.frame_id = frame_id;
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

            const auto outputs = session.forward(inputs);
            if (outputs.size() != 1) throw std::runtime_error("unexpected output count");
            if (!outputs[0].waitForReady(kReadyTimeout)) out.timed_out = true;
            else {
                out.logits = read_fp32_logits(outputs[0]);
                out.has_logits = !out.logits.empty();
            }
            out.forward_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
        }
    } catch (const std::exception& e) {
        out.errored = true;
        out.err = e.what();
    }

    guard.close_now();
    if (!close_err.empty()) {
        out.errored = true;
        if (out.err.empty()) out.err = close_err;
        else out.err += " | " + close_err;
    }
    return out;
}

void emit_sequence_line(Rearm rearm, int round, const FrameOut& f, const std::map<int, int>& ref,
                        int& matched, int& compared, int& delay_matched, int& delay_compared,
                        int& timeout, int& error, int& previous_ref_id) {
    const bool has_ref = ref.count(f.frame_id);
    const int ref_id = has_ref ? ref.at(f.frame_id) : -1;

    std::cout << "RT_FRAME rearm=" << rearm_name(rearm) << " round=" << round
              << " frame=" << f.frame_id;

    if (f.errored) {
        ++error;
        std::cout << " pred=-1 ref=" << ref_id << " result=ERROR wait=ERR setup=-1.000 forward=-1.000 err=" << f.err;
    } else if (f.timed_out) {
        ++timeout;
        const long pred = f.has_logits ? static_cast<long>(argmax(f.logits)) : -1;
        std::cout << " pred=" << pred << " ref=" << ref_id << " result=TIMEOUT wait=TIMEOUT"
                  << " setup=" << std::fixed << std::setprecision(3) << f.setup_ms
                  << " forward=" << f.forward_ms;
    } else if (!f.has_logits) {
        ++error;
        std::cout << " pred=-1 ref=" << ref_id << " result=ERROR wait=ERR setup=" << f.setup_ms
                  << " forward=-1.000";
    } else {
        const long pred = static_cast<long>(argmax(f.logits));
        std::string result = "NO_REF";
        if (has_ref) {
            ++compared;
            if (pred == ref_id) { ++matched; result = "MATCH"; }
            else result = "MISMATCH";
        }
        char delay = '-';
        // A repeated class in adjacent inputs is not evidence of stale output.
        // Count the delay diagnostic only when the immediately preceding input
        // had a different expected class, including the 18 -> 7 cycle boundary.
        if (has_ref && previous_ref_id >= 0 && previous_ref_id != ref_id) {
            ++delay_compared;
            if (pred == previous_ref_id) { ++delay_matched; delay = 'y'; }
            else delay = 'n';
        }
        std::cout << " pred=" << pred << " ref=" << ref_id << " result=" << result << " delay=" << delay
                  << " setup=" << std::fixed << std::setprecision(3) << f.setup_ms
                  << " forward=" << f.forward_ms << " wait=OK";
    }
    if (f.has_layers) std::cout << " layer_b=" << f.layer_before << " layer_a=" << f.layer_after;
    std::cout << '\n';
    if (has_ref) previous_ref_id = ref_id;
}

// Sequence test: persistent Device + persistent Session (unless --rearm reopen),
// cycle frames kCycleFirst..kCycleLast to reach `frames` total, argmax vs ref.
void run_sequence(const Options& opt, const std::vector<char>& payload,
                  const std::map<int, int>& ref, Rearm rearm) {
    const std::size_t frame_count = payload.size() / kFrameBytes;
    if (static_cast<std::size_t>(kCycleLast) >= frame_count) {
        throw std::runtime_error("tensor file has fewer frames than the sequence range");
    }

    auto network = icraft::xir::Network::CreateFromJsonFile(opt.model);
    network.lazyLoadParamsFromFile(opt.raw);
    if (network.inputs().size() != 2 || network.outputs().size() != 1) {
        throw std::runtime_error("compiled network must have exactly two inputs and one output");
    }

    int matched = 0, compared = 0, delay_matched = 0, delay_compared = 0, timeout = 0, error = 0;
    int previous_ref_id = -1;
    std::vector<double> setup_ms_all, forward_ms_all;

    if (rearm == Rearm::Reopen) {
        // Control: fresh Device per frame.
        for (int i = 0; i < opt.frames; ++i) {
            const int frame_id = kCycleFirst + (i % (kCycleLast - kCycleFirst + 1));
            const char* frame = payload.data() + static_cast<std::size_t>(frame_id) * kFrameBytes;
            FrameOut out = forward_read_reopen(network, frame, frame_id);
            if (out.setup_ms >= 0.0) setup_ms_all.push_back(out.setup_ms);
            if (out.forward_ms >= 0.0) forward_ms_all.push_back(out.forward_ms);
            emit_sequence_line(rearm, opt.rounds, out, ref, matched, compared, delay_matched, delay_compared, timeout, error, previous_ref_id);
        }
    } else {
        auto device = icraft::xrt::Device::Open(kDeviceUrl);
        auto zg = device.cast<icraft::xrt::ZG330Device>();
        auto session = icraft::xrt::Session::Create<ZG330Backend, HostBackend>(
            network, { device, icraft::xrt::HostDevice::Default() });
        session.apply();

        for (int i = 0; i < opt.frames; ++i) {
            const int frame_id = kCycleFirst + (i % (kCycleLast - kCycleFirst + 1));
            const char* frame = payload.data() + static_cast<std::size_t>(frame_id) * kFrameBytes;

            std::vector<float> iq(kIqBytes), phys(kPhysicalBytes);
            dequantize(frame, iq, phys);

            const auto t_setup = std::chrono::steady_clock::now();
            const auto inputs = make_inputs(network, iq, phys, icraft::xrt::HostDevice::MemRegion());
            const double setup_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t_setup).count();
            FrameOut out;
            out.frame_id = frame_id;
            try {
                out = forward_read_persistent(session, device, zg, inputs, frame_id, rearm, i == 0, true);
            } catch (const std::exception& e) {
                out.errored = true;
                out.err = e.what();
            }
            out.setup_ms = setup_ms;   // per-frame input-build only (no Session/Device rebuild)
            if (out.setup_ms >= 0.0) setup_ms_all.push_back(out.setup_ms);
            if (out.forward_ms >= 0.0) forward_ms_all.push_back(out.forward_ms);
            emit_sequence_line(rearm, opt.rounds, out, ref, matched, compared, delay_matched, delay_compared, timeout, error, previous_ref_id);
        }
        icraft::xrt::Device::Close(device);
    }

    std::cout << "RT_SUMMARY rearm=" << rearm_name(rearm) << " test=sequence frames=" << opt.frames
              << " match=" << matched << "/" << compared
              << " delay_shift=" << delay_matched << "/" << delay_compared
              << " timeout=" << timeout << " error=" << error;
    if (!forward_ms_all.empty()) {
        std::cout << " forward_avg=" << std::fixed << std::setprecision(3) << mean(forward_ms_all)
                  << " forward_max=" << maximum(forward_ms_all);
    }
    if (!setup_ms_all.empty()) {
        std::cout << " setup_avg=" << std::fixed << std::setprecision(3) << mean(setup_ms_all)
                  << " setup_max=" << maximum(setup_ms_all);
    }
    std::cout << '\n';

    const bool pass = (compared == opt.frames && matched == compared &&
                       delay_matched == 0 && timeout == 0 && error == 0);
    std::cout << (pass ? "RT_RESULT=PASS" : "RT_RESULT=FAIL") << '\n';
}

// Alternating test: capture true logits for frame A and frame B via the known-
// good reopen path, then alternate A/B on a PERSISTENT device and compare each
// output's FULL logits (not just argmax) to its own frame's baseline.  A stale
// result surfaces as a large logits diff against the frame it claims to be.
void run_alternating(const Options& opt, const std::vector<char>& payload,
                     const std::map<int, int>& ref, Rearm rearm) {
    const std::size_t frame_count = payload.size() / kFrameBytes;
    if (static_cast<std::size_t>(kAltFrameA) >= frame_count || static_cast<std::size_t>(kAltFrameB) >= frame_count) {
        throw std::runtime_error("alternating frame index out of range");
    }

    auto network = icraft::xir::Network::CreateFromJsonFile(opt.model);
    network.lazyLoadParamsFromFile(opt.raw);

    const char* frame_a = payload.data() + static_cast<std::size_t>(kAltFrameA) * kFrameBytes;
    const char* frame_b = payload.data() + static_cast<std::size_t>(kAltFrameB) * kFrameBytes;

    // Baseline via reopen control (the known 12/12 path).
    const FrameOut base_a = forward_read_reopen(network, frame_a, kAltFrameA);
    const FrameOut base_b = forward_read_reopen(network, frame_b, kAltFrameB);
    if (base_a.errored || !base_a.has_logits) throw std::runtime_error("alternating baseline frame A failed");
    if (base_b.errored || !base_b.has_logits) throw std::runtime_error("alternating baseline frame B failed");

    const double ab_diff = max_abs_diff(base_a.logits, base_b.logits);
    std::cout << "RT_ALT_BASELINE frameA=" << kAltFrameA << " argmax=" << argmax(base_a.logits)
              << " frameB=" << kAltFrameB << " argmax=" << argmax(base_b.logits)
              << " logits_diff_AB=" << std::scientific << std::setprecision(4) << ab_diff << '\n';

    int iterations = opt.alt_iterations;
    int stale = 0, argmax_mismatch = 0, timeout = 0, error = 0;
    double worst_diff = 0.0;
    std::vector<double> forward_ms_all;

    auto device = icraft::xrt::Device::Open(kDeviceUrl);
    auto zg = device.cast<icraft::xrt::ZG330Device>();
    auto session = icraft::xrt::Session::Create<ZG330Backend, HostBackend>(
        network, { device, icraft::xrt::HostDevice::Default() });
    session.apply();

    for (int i = 0; i < iterations; ++i) {
        const int frame_id = ((i % 2) == 0) ? kAltFrameA : kAltFrameB;
        const char* frame = payload.data() + static_cast<std::size_t>(frame_id) * kFrameBytes;
        std::vector<float> iq(kIqBytes), phys(kPhysicalBytes);
        dequantize(frame, iq, phys);

        const auto inputs = make_inputs(network, iq, phys, icraft::xrt::HostDevice::MemRegion());
        FrameOut out;
        out.frame_id = frame_id;
        try {
            out = forward_read_persistent(session, device, zg, inputs, frame_id, rearm, i == 0, false);
        } catch (const std::exception& e) {
            out.errored = true;
            out.err = e.what();
        }

        const int ref_id = ref.count(frame_id) ? ref.at(frame_id) : -1;
        if (out.errored) {
            ++error;
            std::cout << "RT_ALT i=" << i << " frame=" << frame_id << " result=ERROR err=" << out.err << '\n';
            continue;
        }
        if (out.timed_out) {
            ++timeout;
            std::cout << "RT_ALT i=" << i << " frame=" << frame_id << " result=TIMEOUT\n";
            continue;
        }
        if (!out.has_logits) {
            ++error;
            std::cout << "RT_ALT i=" << i << " frame=" << frame_id << " result=ERROR (no logits)\n";
            continue;
        }

        const auto& base = (frame_id == kAltFrameA) ? base_a.logits : base_b.logits;
        const double diff = max_abs_diff(out.logits, base);
        worst_diff = std::max(worst_diff, diff);
        const bool is_stale = diff > kLogitTol;
        if (is_stale) ++stale;

        const long pred = static_cast<long>(argmax(out.logits));
        const bool arg_ok = (ref_id < 0) || (pred == ref_id);
        if (!arg_ok) ++argmax_mismatch;

        std::cout << "RT_ALT i=" << i << " frame=" << frame_id << " pred=" << pred << " ref=" << ref_id
                  << " argmax_ok=" << (arg_ok ? "yes" : "no")
                  << " logits_diff=" << std::scientific << std::setprecision(4) << diff
                  << (is_stale ? " stale=YES" : " stale=no")
                  << " forward=" << std::fixed << std::setprecision(3) << out.forward_ms << '\n';
        if (out.forward_ms >= 0.0) forward_ms_all.push_back(out.forward_ms);
    }

    icraft::xrt::Device::Close(device);

    std::cout << "RT_ALT_SUMMARY rearm=" << rearm_name(rearm) << " iterations=" << iterations
              << " stale=" << stale << " argmax_mismatch=" << argmax_mismatch
              << " timeout=" << timeout << " error=" << error
              << " worst_logits_diff=" << std::scientific << std::setprecision(4) << worst_diff;
    if (!forward_ms_all.empty()) {
        std::cout << " forward_avg=" << std::fixed << std::setprecision(3) << mean(forward_ms_all)
                  << " forward_max=" << maximum(forward_ms_all);
    }
    std::cout << '\n';

    const bool pass = (stale == 0 && argmax_mismatch == 0 && timeout == 0 && error == 0 && ab_diff > kLogitTol);
    std::cout << (pass ? "RT_RESULT=PASS" : "RT_RESULT=FAIL") << '\n';
}

Options parse_args(int argc, char** argv) {
    Options opt;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        auto next = [&](const char* name) -> std::string {
            if (i + 1 >= argc) throw std::runtime_error(std::string("missing value for ") + name);
            return argv[++i];
        };
        if (a == "--model") opt.model = next("--model");
        else if (a == "--raw") opt.raw = next("--raw");
        else if (a == "--tensor") opt.tensor = next("--tensor");
        else if (a == "--reference") opt.reference = next("--reference");
        else if (a == "--rearm") opt.rearm = next("--rearm");
        else if (a == "--test") opt.test = next("--test");
        else if (a == "--frames") opt.frames = std::stoi(next("--frames"));
        else if (a == "--alt-iterations") opt.alt_iterations = std::stoi(next("--alt-iterations"));
        else if (a == "--rounds") opt.rounds = std::stoi(next("--rounds"));
        else throw std::runtime_error("unknown argument: " + a);
    }
    if (opt.model.empty() || opt.raw.empty() || opt.tensor.empty()) {
        throw std::runtime_error("--model, --raw and --tensor are required");
    }
    if (opt.test != "sequence" && opt.test != "alternating") {
        throw std::runtime_error("--test must be 'sequence' or 'alternating'");
    }
    if (opt.frames < 1) throw std::runtime_error("--frames must be >= 1");
    if (opt.rounds < 1) throw std::runtime_error("--rounds must be >= 1");
    return opt;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const Options opt = parse_args(argc, argv);
        const Rearm rearm = parse_rearm(opt.rearm);

        const auto payload = read_binary(opt.tensor);
        if (payload.empty() || payload.size() % kFrameBytes != 0) {
            throw std::runtime_error("tensor file size must be a non-zero multiple of 5120 bytes");
        }
        const std::map<int, int> ref = opt.reference.empty() ? std::map<int, int>{} : load_reference_argmax(opt.reference);

        if (opt.test == "alternating") {
            run_alternating(opt, payload, ref, rearm);
        } else {
            run_sequence(opt, payload, ref, rearm);
        }
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "RT_ERROR: " << e.what() << '\n';
        return 1;
    }
}
