// NPU-only board smoke test for the frozen TimePowerPhase RF partition.
//
// Compiled contract (verified in compiled_model_gate/): the ZG330 network takes
// TWO FP32 inputs -- iq [1,2,1024] and physical_features [1,3,1024] -- and
// emits ONE FP32 output, logits [1,8].  The FPGA Mandatory Core emits a five
// plane SInt8 tensor; this program performs the frozen host-side dequantization
// (iq x 1/127, physical x 2/127) and feeds FP32 to the NPU.
//
// The session binds BOTH ZG330Backend and HostBackend: in the compiled model the
// Input/Output ops are @hostt while the 85 compute HardOps are @zhuget(330), so
// the HostBackend owns the input/output tensors and the ZG330Backend owns the
// NPU compute.  To avoid an iCraft 3.39 session/buffer-reuse artifact (a reused
// session can hand back a stale, already-"ready" output tensor and thus report
// the PREVIOUS frame's result -- the observed fixed one-frame delay), every
// frame runs in a FRESH Session with FRESH input/output tensors.  The Device and
// Network are created exactly once.
//
// Usage:
//   npu_only_smoke --model model.json --raw model.raw --tensor tensor.bin \
//                  --frame 7 [--reference reference_argmax.txt]
//   npu_only_smoke --model model.json --raw model.raw --tensor tensor.bin \
//                  --frames 7 18 [--reference reference_argmax.txt]
//   npu_only_smoke --model model.json --raw model.raw --tensor tensor.bin \
//                  --all-frames [--reference reference_argmax.txt]
//
// gnu++17. No /dev/mem, no kernel driver, no AXI DMA here -- only the official
// icraft-xrt / icraft-xir / ZG330Backend / HostBackend APIs.

#include <icraft-backends/zg330backend/zg330backend.h>
#include <icraft-backends/hostbackend/backend.h>
#include <icraft-xir/core/network.h>
#include <icraft-xrt/core/device.h>
#include <icraft-xrt/core/session.h>
#include <icraft-xrt/core/tensor.h>
#include <icraft-xrt/dev/host_device.h>

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
constexpr std::size_t kFrameBytes = kPlanes * kFrameLength;   // 5120
constexpr std::size_t kIqBytes = 2 * kFrameLength;            // 2048 int8 / 8192 B fp32
constexpr std::size_t kPhysicalBytes = 3 * kFrameLength;      // 3072 int8 / 12288 B fp32
constexpr float kIqScale = 1.0f / 127.0f;
constexpr float kPhysicalScale = 2.0f / 127.0f;
constexpr const char* kDeviceUrl = "axi://zg330aiu?npu=0x40000000&dma=0x80000000";
constexpr const char* kClasses[8] = {"BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"};
constexpr std::chrono::milliseconds kReadyTimeout{10000};

struct Options {
    std::string model;
    std::string raw;
    std::string tensor;
    std::string reference;
    int first = -1;
    int last = -1;   // inclusive; -1 means "single frame [first]"
    bool all_frames = false;
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

void print_value_contract(const char* direction, std::size_t index, const icraft::xir::Value& value) {
    const auto dtype = value.tensorType();
    std::cout << direction << '[' << index << "] shape=[";
    for (std::size_t i = 0; i < dtype->shape.size(); ++i) {
        if (i) std::cout << ',';
        std::cout << dtype->shape[i];
    }
    const auto storage = dtype->element_dtype.getStorageType();
    std::cout << "] layout=" << dtype->layout.toString()
              << " storage=" << storage->typeKey()
              << " bytes=" << dtype.bytes();
    std::cout << '\n';
}

icraft::xrt::Tensor make_fp32_input(const icraft::xir::Value& value, const float* source, std::size_t element_count) {
    const auto dtype = value.tensorType();
    const auto storage = dtype->element_dtype.getStorageType();
    if (!storage.isFP32()) {
        throw std::runtime_error("compiled input storage is not FP32; the adapter must feed dequantized FP32");
    }
    const std::size_t byte_count = element_count * sizeof(float);
    if (dtype.bytes() != byte_count) {
        throw std::runtime_error("compiled input byte size differs from contiguous FP32 NCL");
    }
    auto tensor = icraft::xrt::Tensor(value).mallocOn(icraft::xrt::HostDevice::MemRegion());
    tensor.write(0, const_cast<char*>(reinterpret_cast<const char*>(source)), byte_count);
    return tensor;
}

std::vector<float> read_fp32_logits(const icraft::xrt::Tensor& tensor) {
    const auto dtype = tensor.dtype();
    std::vector<char> bytes(dtype.bytes());
    auto host = tensor.to(icraft::xrt::HostDevice::MemRegion());
    host.read(bytes.data(), 0, bytes.size());
    if (bytes.size() != 8 * sizeof(float)) {
        throw std::runtime_error("unexpected logits storage/size; expected 8 x FP32");
    }
    std::vector<float> logits(8);
    std::memcpy(logits.data(), bytes.data(), bytes.size());
    return logits;
}

std::vector<float> softmax(const std::vector<float>& logits) {
    std::vector<float> result(logits.size());
    const float mx = *std::max_element(logits.begin(), logits.end());
    float sum = 0.0f;
    for (std::size_t i = 0; i < logits.size(); ++i) {
        result[i] = std::exp(logits[i] - mx);
        sum += result[i];
    }
    for (auto& v : result) v /= sum;
    return result;
}

std::size_t argmax(const std::vector<float>& values) {
    return static_cast<std::size_t>(std::distance(values.begin(), std::max_element(values.begin(), values.end())));
}

// reference_argmax.txt: header "frame_id,argmax_id,argmax_class,ood,ground_truth"
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
        const int frame_id = std::stoi(cols[0]);
        const int argmax_id = std::stoi(cols[1]);
        const bool ood = (cols[3] == "1");
        if (!ood) ref[frame_id] = argmax_id;
    }
    return ref;
}

Options parse_args(int argc, char** argv) {
    Options opt;
    int mode = 0;  // 0 none, 1 --frame, 2 --frames, 3 --all-frames
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
        else if (a == "--frame") { opt.first = std::stoi(next("--frame")); opt.last = -1; mode = 1; }
        else if (a == "--frames") { opt.first = std::stoi(next("--frames")); opt.last = std::stoi(next("--frames")); mode = 2; }
        else if (a == "--all-frames") { opt.all_frames = true; mode = 3; }
        else throw std::runtime_error("unknown argument: " + a);
    }
    if (opt.model.empty() || opt.raw.empty() || opt.tensor.empty()) {
        throw std::runtime_error("--model, --raw and --tensor are required");
    }
    if (mode == 0) throw std::runtime_error("specify --frame N, --frames N M, or --all-frames");
    if (mode == 2 && opt.last < opt.first) throw std::runtime_error("--frames: last must be >= first");
    if (opt.first < 0) throw std::runtime_error("frame index must be >= 0");
    return opt;
}

std::vector<int> build_frame_indices(const Options& opt, std::size_t frame_count) {
    std::vector<int> v;
    if (opt.all_frames) {
        for (std::size_t i = 0; i < frame_count; ++i) v.push_back(static_cast<int>(i));
    } else if (opt.last < 0) {
        v.push_back(opt.first);
    } else {
        for (int i = opt.first; i <= opt.last; ++i) v.push_back(i);
    }
    return v;
}

struct FrameResult {
    int frame_id = -1;
    std::vector<float> logits;
    double setup_ms = 0.0;
    double forward_ms = 0.0;
};

// Run one frame end-to-end in a FRESH session.  The session and its input/output
// tensors are destroyed when this function returns; only the copied logits (a
// plain std::vector<float>) and the timings escape the scope.
FrameResult run_one_frame(const icraft::xir::Network& network,
                          const icraft::xrt::Device& device,
                          int frame_id,
                          const char* frame_bytes) {
    const int8_t* iq_int8 = reinterpret_cast<const int8_t*>(frame_bytes);
    const int8_t* physical_int8 = reinterpret_cast<const int8_t*>(frame_bytes + kIqBytes);

    std::vector<float> iq_fp32(kIqBytes);
    std::vector<float> physical_fp32(kPhysicalBytes);
    for (std::size_t i = 0; i < kIqBytes; ++i) iq_fp32[i] = static_cast<float>(iq_int8[i]) * kIqScale;
    for (std::size_t i = 0; i < kPhysicalBytes; ++i) physical_fp32[i] = static_cast<float>(physical_int8[i]) * kPhysicalScale;

    const auto t_setup_start = std::chrono::steady_clock::now();

    // Fresh input tensors and a fresh session, scoped to this frame only.
    std::vector<icraft::xrt::Tensor> inputs;
    inputs.reserve(2);
    for (std::size_t i = 0; i < network.inputs().size(); ++i) {
        const auto value = network.inputs()[i];
        const auto shape = shape_of(value);
        if (same_shape(shape, {1, 2, 1024})) {
            inputs.push_back(make_fp32_input(value, iq_fp32.data(), kIqBytes));
        } else if (same_shape(shape, {1, 3, 1024})) {
            inputs.push_back(make_fp32_input(value, physical_fp32.data(), kPhysicalBytes));
        } else {
            throw std::runtime_error("unexpected compiled input shape");
        }
    }

    auto session = icraft::xrt::Session::Create<icraft::xrt::zg330::ZG330Backend, icraft::xrt::HostBackend>(
        network, { device, icraft::xrt::HostDevice::Default() });
    session.apply();

    const auto t_setup_end = std::chrono::steady_clock::now();
    const double setup_ms = std::chrono::duration<double, std::milli>(t_setup_end - t_setup_start).count();

    const auto t_fwd_start = std::chrono::steady_clock::now();
    const auto outputs = session.forward(inputs);
    if (outputs.size() != 1) {
        throw std::runtime_error("unexpected output count from NPU session");
    }
    if (!outputs[0].waitForReady(kReadyTimeout)) {
        throw std::runtime_error("NPU inference did not become ready within timeout");
    }
    // Copy this frame's output into a plain buffer BEFORE the session and its
    // tensors are destroyed, so nothing borrowed from the session outlives it.
    const std::vector<float> logits = read_fp32_logits(outputs[0]);
    const double forward_ms = std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - t_fwd_start).count();

    return FrameResult{frame_id, logits, setup_ms, forward_ms};
}

double mean(const std::vector<double>& v) {
    if (v.empty()) return 0.0;
    double s = 0.0;
    for (const double x : v) s += x;
    return s / static_cast<double>(v.size());
}

double maximum(const std::vector<double>& v) {
    if (v.empty()) return 0.0;
    return *std::max_element(v.begin(), v.end());
}

}  // namespace

int main(int argc, char** argv) {
    icraft::xrt::Device device;
    bool device_open = false;
    try {
        const Options opt = parse_args(argc, argv);

        const auto payload = read_binary(opt.tensor);
        if (payload.empty() || payload.size() % kFrameBytes != 0) {
            throw std::runtime_error("Tensor file size must be a non-zero multiple of 5120 bytes");
        }
        const std::size_t frame_count = payload.size() / kFrameBytes;
        if (static_cast<std::size_t>(opt.first) >= frame_count ||
            (opt.last >= 0 && static_cast<std::size_t>(opt.last) >= frame_count)) {
            throw std::runtime_error("frame index is out of range");
        }

        auto network = icraft::xir::Network::CreateFromJsonFile(opt.model);
        network.lazyLoadParamsFromFile(opt.raw);
        if (network.inputs().size() != 2 || network.outputs().size() != 1) {
            throw std::runtime_error("compiled network must have exactly two inputs and one output");
        }
        for (std::size_t i = 0; i < network.inputs().size(); ++i) {
            print_value_contract("input", i, network.inputs()[i]);
        }
        print_value_contract("output", 0, network.outputs()[0]);

        // Device and Network are initialized exactly once, outside the frame loop.
        device = icraft::xrt::Device::Open(kDeviceUrl);
        device_open = true;

        const std::map<int, int> reference = opt.reference.empty() ? std::map<int, int>{} : load_reference_argmax(opt.reference);
        const std::vector<int> frame_indices = build_frame_indices(opt, frame_count);

        int matched = 0;
        int compared = 0;
        bool any_fail = false;
        std::vector<double> setup_ms_all;
        std::vector<double> forward_ms_all;

        for (const int frame_id : frame_indices) {
            const char* frame = payload.data() + static_cast<std::size_t>(frame_id) * kFrameBytes;
            const FrameResult r = run_one_frame(network, device, frame_id, frame);
            setup_ms_all.push_back(r.setup_ms);
            forward_ms_all.push_back(r.forward_ms);

            const auto probs = softmax(r.logits);
            const std::size_t best = argmax(r.logits);

            std::cout << "frame=" << frame_id << "  argmax=" << best << "  class=" << kClasses[best]
                      << "  conf=" << std::fixed << std::setprecision(4) << probs[best]
                      << "  setup=" << std::setprecision(3) << r.setup_ms
                      << " ms  forward=" << r.forward_ms << " ms\n";
            std::cout << "  logits=[";
            for (std::size_t i = 0; i < r.logits.size(); ++i) {
                if (i) std::cout << ", ";
                std::cout << std::setprecision(4) << r.logits[i];
            }
            std::cout << "]\n";

            if (reference.count(frame_id)) {
                ++compared;
                const int ref_best = reference.at(frame_id);
                const bool ok = (static_cast<int>(best) == ref_best);
                if (ok) ++matched; else any_fail = true;
                std::cout << "  reference_argmax=" << ref_best << " (" << kClasses[ref_best] << ")  "
                          << (ok ? "MATCH" : "MISMATCH") << '\n';
            }
        }

        icraft::xrt::Device::Close(device);
        device_open = false;

        std::cout << "processed_frames=" << frame_indices.front() << ".." << frame_indices.back()
                  << " (" << frame_indices.size() << " frames)\n";
        std::cout << "forward_time: avg=" << std::fixed << std::setprecision(3) << mean(forward_ms_all)
                  << " ms, max=" << maximum(forward_ms_all) << " ms\n";
        std::cout << "setup_time:   avg=" << std::fixed << std::setprecision(3) << mean(setup_ms_all)
                  << " ms, max=" << maximum(setup_ms_all) << " ms\n";

        if (reference.empty()) {
            std::cout << "V2_NPU_ONLY_SMOKE_PASS (no reference comparison requested)\n";
        } else {
            std::cout << "class_match=" << matched << "/" << compared << " valid frames\n";
            std::cout << (any_fail ? "V2_NPU_ONLY_SMOKE_REFERENCE_MISMATCH\n" : "V2_NPU_ONLY_SMOKE_REFERENCE_MATCH\n");
            if (any_fail) return 1;
        }
        return 0;
    } catch (const std::exception& error) {
        if (device_open) {
            icraft::xrt::Device::Close(device);
        }
        std::cerr << "V2_NPU_ONLY_SMOKE_FAIL: " << error.what() << '\n';
        return 1;
    }
}
