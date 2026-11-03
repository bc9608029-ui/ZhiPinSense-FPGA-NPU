#pragma once
// probe_common.hpp — board-side shared helpers for the M27.1 multi-model probes.
//
// Board-only: builds against the iCraft 3.39 SDK (ZG330Backend + HostBackend).
// Lifecycle mirrors the production chain's board-proven discipline
// (npu_classifier.hpp): the Device is opened ONCE, a single Session is created
// and apply()ed ONCE, and every frame after the first runs Device::reset(1)
// before forward — never per-frame Device::Open, never per-frame apply().
// See the M27 audit §13 for why reset(1) re-arms the ZG330 monotonic completion
// state (the fixed one-frame-delay artifact behind Gate 7).
//
// Fail-closed: every contract/runtime failure throws; the caller maps it to a
// non-zero exit + a FAIL result.  Never a silent HostBackend fallback.

#include <icraft-backends/zg330backend/zg330backend.h>
#include <icraft-backends/hostbackend/backend.h>
#include <icraft-xir/core/network.h>
#include <icraft-xrt/core/device.h>
#include <icraft-xrt/core/session.h>
#include <icraft-xrt/core/tensor.h>
#include <icraft-xrt/dev/host_device.h>

#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

#include "m27_1_metrics.hpp"

namespace m27_1 {

constexpr const char* kNpuDeviceUrl =
    "axi://zg330aiu?npu=0x40000000&dma=0x80000000";
constexpr std::size_t kTensorFloats = 2048;  // [1,2,1024] fp32
constexpr std::int64_t kReadyTimeoutMs = 10000;

// A compiled model the probe drives.  Paths point at the board's existing frozen
// model files (sha256-checked by the shell script before the probe runs).
struct ModelSpec {
    std::string label;        // "A" or "B"
    std::string json_path;    // model.json
    std::string raw_path;     // model.raw
    std::int64_t out_count;   // A=12, B=8
};

// Open the ZG330 device handle once.  Device is a copyable handle, so several
// sessions may share one handle (multiple Network/Session under a single Device).
inline icraft::xrt::Device open_zg330_device() {
    return icraft::xrt::Device::Open(kNpuDeviceUrl);
}

// One persistent model session: Network+Session created and applied once.
// infer() runs the reset(1)-per-frame discipline.  The session may either open
// its own Device (owns=true) or share an externally-opened one (owns=false).
class Zg330Session {
public:
    // Open its own device (probe_single_model, probe_unload_reload).
    explicit Zg330Session(const ModelSpec& spec)
        : Zg330Session(spec, open_zg330_device(), true) {}

    // Share an already-open device (probe_two_networks, probe_sequential,
    // probe_concurrent): multiple sessions on ONE Device, no re-open.
    Zg330Session(const ModelSpec& spec, icraft::xrt::Device device, bool owns)
        : spec_(spec),
          network_(icraft::xir::Network::CreateFromJsonFile(spec.json_path)) {
        const double t0 = now_us();
        network_.lazyLoadParamsFromFile(spec.raw_path);
        model_load_us = elapsed_us(t0);
        check_contract();
        device_ = device;
        owns_ = owns;
        const double t1 = now_us();
        session_ = icraft::xrt::Session::Create<
            icraft::xrt::zg330::ZG330Backend, icraft::xrt::HostBackend>(
            network_, {device_, icraft::xrt::HostDevice::Default()});
        session_.apply();
        session_apply_us = elapsed_us(t1);
        inputs_.reserve(1);
    }

    ~Zg330Session() {
        if (owns_) icraft::xrt::Device::Close(device_);
    }

    Zg330Session(const Zg330Session&) = delete;
    Zg330Session& operator=(const Zg330Session&) = delete;

    std::int64_t out_count() const { return spec_.out_count; }
    const std::string& label() const { return spec_.label; }
    double model_load_us = -1.0;      // CreateFromJsonFile + lazyLoadParamsFromFile
    double session_apply_us = -1.0;   // Session::Create + apply()

    // Run one inference: write `out_count()` fp32 logits into `out`.  Throws on
    // any contract/runtime failure (fail-closed).
    void infer(const float* iq, float* out) {
        const auto input_value = network_.inputs()[0];
        const auto dtype = input_value.tensorType();
        const auto storage = dtype->element_dtype.getStorageType();
        if (!storage.isFP32())
            throw std::runtime_error("compiled input storage is not FP32");
        const std::size_t byte_count = kTensorFloats * sizeof(float);
        if (dtype.bytes() != byte_count)
            throw std::runtime_error(
                "compiled input byte size differs from [1,2,1024] fp32");

        auto input_tensor =
            icraft::xrt::Tensor(input_value).mallocOn(icraft::xrt::HostDevice::MemRegion());
        input_tensor.write(0,
                           const_cast<char*>(reinterpret_cast<const char*>(iq)),
                           byte_count);
        inputs_.clear();
        inputs_.push_back(std::move(input_tensor));

        // First frame runs on freshly-initialized hardware; every frame after it
        // gets exactly one reset(1) and no re-apply (production discipline).
        if (frames_ > 0) device_.reset(1);
        ++frames_;

        const auto outputs = session_.forward(inputs_);
        if (outputs.size() != 1)
            throw std::runtime_error("unexpected output count from NPU session");
        if (!outputs[0].waitForReady(kReadyTimeoutMs))
            throw std::runtime_error("NPU inference not ready within timeout");
        read_logits(outputs[0], out);
    }

private:
    static std::vector<std::int64_t> shape_of(const icraft::xir::Value& v) {
        std::vector<std::int64_t> s;
        for (const auto d : v.tensorType()->shape) s.push_back(d);
        return s;
    }

    void check_contract() {
        if (network_.inputs().size() != 1 || network_.outputs().size() != 1)
            throw std::runtime_error("probe model must have exactly one input/output");
        const auto in = shape_of(network_.inputs()[0]);
        if (in.size() != 3 || in[0] != 1 || in[1] != 2 || in[2] != 1024)
            throw std::runtime_error("unexpected input shape (expected [1,2,1024])");
        const auto out = shape_of(network_.outputs()[0]);
        if (out.size() != 2 || out[0] != 1 || out[1] != spec_.out_count)
            throw std::runtime_error("unexpected output shape for probe model");
    }

    void read_logits(const icraft::xrt::Tensor& tensor, float* out) {
        const auto dtype = tensor.dtype();
        read_buf_.resize(dtype.bytes());
        auto host = tensor.to(icraft::xrt::HostDevice::MemRegion());
        host.read(read_buf_.data(), 0, read_buf_.size());
        if (read_buf_.size() != static_cast<std::size_t>(spec_.out_count) * sizeof(float))
            throw std::runtime_error("unexpected logits byte size");
        std::memcpy(out, read_buf_.data(), read_buf_.size());
    }

    ModelSpec spec_;
    icraft::xir::Network network_;
    icraft::xrt::Device device_;
    bool owns_ = false;
    icraft::xrt::Session session_;
    std::uint64_t frames_ = 0;
    std::vector<icraft::xrt::Tensor> inputs_;
    std::vector<char> read_buf_;
};

// Minimal "--key value" argument lookup (board probes only; the shell script
// pre-validates paths and SHA256 before invoking the probe).
inline std::string arg_value(int argc, char** argv, const std::string& key,
                             const std::string& def = "") {
    for (int i = 1; i + 1 < argc; ++i)
        if (std::string(argv[i]) == key) return std::string(argv[i + 1]);
    return def;
}

// Coarse process RSS (resident set size) in KiB, for the memory-growth check in
// probe_sequential/probe_unload_reload.  Linux-only; returns -1 when unavailable.
inline long read_rss_kb() {
    FILE* f = std::fopen("/proc/self/statm", "r");
    if (!f) return -1;
    long pages = -1;
    // statm: size resident shared text lib data dt — resident is field 2 (pages).
    if (std::fscanf(f, "%*ld %ld", &pages) != 1) pages = -1;
    std::fclose(f);
    if (pages < 0) return -1;
    return pages * 4;  // 4 KiB pages (typical; ARM Linux page size may differ)
}

// Load a fixed IQ frame from a raw float file (2048 fp32), or synthesize a
// deterministic one when the path is empty (probes only need a well-formed
// input; correctness is judged against logits, not the input source).
inline std::vector<float> load_or_make_iq(const std::string& iq_path) {
    std::vector<float> iq(kTensorFloats, 0.0f);
    if (!iq_path.empty()) {
        FILE* f = std::fopen(iq_path.c_str(), "rb");
        if (!f) throw std::runtime_error("cannot open IQ input file");
        const std::size_t n = std::fread(iq.data(), sizeof(float), kTensorFloats, f);
        std::fclose(f);
        if (n != kTensorFloats)
            throw std::runtime_error("IQ input file too short (need 2048 fp32)");
    } else {
        // Deterministic synthetic frame (sine I / cosine Q at a fixed frequency).
        for (std::size_t i = 0; i < 1024; ++i) {
            const double ph = 0.03125 * 2.0 * 3.14159265358979 * static_cast<double>(i);
            iq[i]      = static_cast<float>(0.25 * std::sin(ph));
            iq[1024+i] = static_cast<float>(0.25 * std::cos(ph));
        }
    }
    return iq;
}

}  // namespace m27_1
