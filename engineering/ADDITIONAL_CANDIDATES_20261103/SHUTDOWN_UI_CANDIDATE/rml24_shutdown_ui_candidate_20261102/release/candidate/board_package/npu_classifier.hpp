#pragma once

// npu_classifier.hpp — iCraft-only, single-input twelve-class NPU inference
// wrapper (task 39e5 Gate 7 / Gate 9).  Board-only: builds on the FMQL30TAI
// Linux image against the iCraft 3.39 SDK (ZG330Backend + HostBackend); it is
// NOT compiled on the host (the host tests cover chain_common.hpp instead).
//
// Model contract (see model_12class/MODEL_DEPLOYMENT_CONTRACT.md):
//   input  iq     [1,2,1024] fp32  @hostt  (plane 0 = I, plane 1 = Q, C-order)
//   output logits [1,12]     fp32  @hostt
//   128 HardOps @zhuget(330); int8 symmetric per-channel quantized interior.
//
// Lifecycle matches the npu_realtime_v1 persistent-Device fix (board-proven
// 12/12, delay shift 0/10): the Device is opened once and a single Session is
// created + apply()ed once.  A fresh per-frame Session does NOT re-arm the
// ZG330's monotonic FPGA completion state, so it returns the PREVIOUS frame's
// output (the fixed one-frame-delay artifact behind Gate 7's matched=3/240).
// Instead, every frame after the first runs Device::reset(1) before forward (and
// never re-applies).  See npu_rearm_state.hpp for the exact discipline.
//
// M22 additions (runtime lifecycle + buffer reuse):
//   * an EXPLICIT lifecycle state machine (npu_lifecycle_state.hpp): open-once /
//     session-apply-once / ready / recovering / failed / close-once.  A transient
//     forward-or-wait failure is retried up to a bounded budget (no re-reset, no
//     reopen); a Device::reset failure is FATAL (fail-closed, close-once via RAII).
//   * infer(tensor, out) writes logits into a caller-provided buffer and reuses
//     the C++ std::vector temporaries (inputs_ reserved once, read_buf_ reused),
//     so the wrapper no longer allocates a fresh output vector / input vector /
//     read buffer per frame.
//   * the iCraft input tensor itself (Tensor.mallocOn) is still created per frame:
//     its copy/move/reuse semantics across session_.forward() calls are SDK-internal
//     and cannot be verified offline, and M21-0/39e5d established it is NOT the
//     root cause.  It is one bounded 8 KB host-memory allocation, not a growing
//     leak; reuse is deferred to a board-verified follow-up.

#include <icraft-backends/zg330backend/zg330backend.h>
#include <icraft-backends/hostbackend/backend.h>
#include <icraft-xir/core/network.h>
#include <icraft-xrt/core/device.h>
#include <icraft-xrt/core/session.h>
#include <icraft-xrt/core/tensor.h>
#include <icraft-xrt/dev/host_device.h>

#include <chrono>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

#include "chain_common.hpp"
#include "npu_rearm_state.hpp"
#include "../sdr_adapter/npu_lifecycle_state.hpp"
#include "../sdr_adapter/latency_stats.hpp"

namespace chain {

constexpr const char* kNpuDeviceUrl =
    "axi://zg330aiu?npu=0x40000000&dma=0x80000000";
constexpr std::chrono::milliseconds kNpuReadyTimeout{10000};
constexpr std::size_t kLogitsCount = 12;

class NpuClassifier12 {
public:
    // The Network is created and its contract checked BEFORE the device is
    // opened, so any malformed-model error leaks no device handle.  An optional
    // m22::StageTiming* records the two one-time bring-up stages (ModelLoad,
    // DeviceOpen) for the M22 runtime baseline; both are startup-only, never in
    // the per-frame hot path.
    explicit NpuClassifier12(const std::string& model_json,
                             const std::string& model_raw,
                             m22::StageTiming* timing = nullptr)
        : network_(icraft::xir::Network::CreateFromJsonFile(model_json)) {
        // ModelLoad: lazy weight load + contract checks.  The JSON parse
        // (Network::CreateFromJsonFile) runs in the member-init list before this
        // body and is a tiny metadata file, not the weights, so it is excluded.
        const auto model_t0 = std::chrono::steady_clock::now();
        network_.lazyLoadParamsFromFile(model_raw);
        if (network_.inputs().size() != 1 || network_.outputs().size() != 1)
            throw std::runtime_error(
                "twelve-class network must have exactly one input and one output");
        check_input_contract();
        check_output_contract();
        if (timing)
            timing->record(m22::StageId::ModelLoad, elapsed_us(model_t0));

        // DeviceOpen: Device::Open + the persistent Session create/apply.  This
        // is the full hardware bring-up (open once, apply once, never per frame).
        const auto dev_t0 = std::chrono::steady_clock::now();
        device_ = icraft::xrt::Device::Open(kNpuDeviceUrl);
        open_ = true;
        lifecycle_.record_open();

        // Persistent Session: created once, apply()ed once.  Re-applying after a
        // Device::reset(1) is a discipline violation (npu_realtime_v1 reset1_apply
        // is rejected), so apply exactly once here and never again.
        session_ = icraft::xrt::Session::Create<
            icraft::xrt::zg330::ZG330Backend, icraft::xrt::HostBackend>(
            network_, { device_, icraft::xrt::HostDevice::Default() });
        session_.apply();
        if (!lifecycle_.record_apply())
            throw std::runtime_error(
                "internal: Session apply() recorded more than once");
        if (!rearm_.record_apply())
            throw std::runtime_error(
                "internal: Session apply() recorded more than once");
        lifecycle_.record_ready();
        if (timing)
            timing->record(m22::StageId::DeviceOpen, elapsed_us(dev_t0));

        inputs_.reserve(1);   // M22: reserve once so push_back never reallocates
    }

    ~NpuClassifier12() {
        lifecycle_.record_close();
        if (open_) icraft::xrt::Device::Close(device_);
    }

    NpuClassifier12(const NpuClassifier12&) = delete;
    NpuClassifier12& operator=(const NpuClassifier12&) = delete;

    // One inference.  `tensor` must hold kTensorFloats floats: the [2,1024]
    // model input in C-order (first 1024 = I, next 1024 = Q).  Returns 12 fp32
    // logits.  Throws on any contract or runtime failure (never a silent
    // HostBackend fallback -- the model is @zhuget(330)).
    std::vector<float> infer(const float* tensor) {
        std::vector<float> logits;
        infer(tensor, logits);
        return logits;
    }

    // M22 allocation-reuse inference: writes 12 fp32 logits into `out`.  Reuses
    // the inputs vector and read buffer; runs the explicit lifecycle state
    // machine with a bounded transient-failure retry.
    void infer(const float* tensor, std::vector<float>& out) {
        const auto input_value = network_.inputs()[0];
        const auto dtype = input_value.tensorType();
        const auto storage = dtype->element_dtype.getStorageType();
        if (!storage.isFP32())
            throw std::runtime_error(
                "compiled input storage is not FP32; the adapter must feed FP32");
        const std::size_t byte_count = kTensorFloats * sizeof(float);
        if (dtype.bytes() != byte_count)
            throw std::runtime_error(
                "compiled input byte size differs from contiguous FP32 [1,2,1024]");

        if (!lifecycle_.begin_frame())
            throw std::runtime_error(
                "NPU lifecycle not ready (device/session not in Ready state)");

        auto input_tensor =
            icraft::xrt::Tensor(input_value).mallocOn(icraft::xrt::HostDevice::MemRegion());
        input_tensor.write(0,
                           const_cast<char*>(reinterpret_cast<const char*>(tensor)),
                           byte_count);
        inputs_.clear();
        inputs_.push_back(std::move(input_tensor));

        // Re-arm the ZG330 FPGA completion state between frames.  The first frame
        // runs on freshly-initialized hardware (no reset); every frame after it
        // gets exactly one Device::reset(1) and NO re-apply() (see header note).
        const bool need_reset = rearm_.begin_frame();
        bool reset_done = false;

        for (;;) {
            try {
                if (need_reset && !reset_done) {
                    device_.reset(1);   // documented: "reset FPGA state only"
                    rearm_.record_reset(true);
                    reset_done = true;
                }
                const auto outputs = session_.forward(inputs_);
                if (outputs.size() != 1)
                    throw std::runtime_error("unexpected output count from NPU session");
                if (!outputs[0].waitForReady(kNpuReadyTimeout))
                    throw std::runtime_error(
                        "NPU inference did not become ready within timeout");
                read_logits(outputs[0], out);
                lifecycle_.record_frame_ok();
                return;
            } catch (...) {
                // A reset failure poisons the re-arm discipline: fatal (fail-closed).
                // A forward/wait failure is transient and retried within the budget.
                if (rearm_.reset_failed()) { lifecycle_.record_fatal(); throw; }
                if (!lifecycle_.record_frame_failure()) throw;
            }
        }
    }

    // Re-arm / session discipline counters (surfaced by Gate 7 for its PASS gate:
    // 240 frames -> reset_count()==239, apply_count()==1, discipline_ok()==true).
    std::uint64_t reset_count() const { return rearm_.reset_count(); }
    std::uint64_t frame_count() const { return rearm_.frame_count(); }
    std::uint64_t apply_count() const { return rearm_.apply_count(); }
    bool reset_failed() const { return rearm_.reset_failed(); }
    bool discipline_ok() const { return rearm_.discipline_ok(); }

    // M22 lifecycle accessors (surfaced on the board result line).
    const NpuLifecycleState& lifecycle() const { return lifecycle_; }

private:
    static std::vector<int64_t> shape_of(const icraft::xir::Value& value) {
        std::vector<int64_t> s;
        for (const auto dim : value.tensorType()->shape) s.push_back(dim);
        return s;
    }

    static double elapsed_us(std::chrono::steady_clock::time_point t0) {
        return std::chrono::duration<double, std::micro>(
            std::chrono::steady_clock::now() - t0).count();
    }

    void check_input_contract() {
        const auto s = shape_of(network_.inputs()[0]);
        if (s.size() != 3 || s[0] != 1 || s[1] != 2 || s[2] != 1024)
            throw std::runtime_error(
                "unexpected compiled input shape (expected [1,2,1024])");
    }

    void check_output_contract() {
        const auto s = shape_of(network_.outputs()[0]);
        if (s.size() != 2 || s[0] != 1 || s[1] != static_cast<int64_t>(kLogitsCount))
            throw std::runtime_error(
                "unexpected compiled output shape (expected [1,12])");
    }

    // Read the host logits into `out`, reusing the member read buffer (M22).
    void read_logits(const icraft::xrt::Tensor& tensor, std::vector<float>& out) {
        const auto dtype = tensor.dtype();
        read_buf_.resize(dtype.bytes());
        auto host = tensor.to(icraft::xrt::HostDevice::MemRegion());
        host.read(read_buf_.data(), 0, read_buf_.size());
        if (read_buf_.size() != kLogitsCount * sizeof(float))
            throw std::runtime_error("unexpected logits size; expected 12 x FP32");
        out.resize(kLogitsCount);
        std::memcpy(out.data(), read_buf_.data(), read_buf_.size());
    }

    icraft::xrt::Device device_;
    bool open_ = false;
    icraft::xir::Network network_;
    icraft::xrt::Session session_;   // persistent, apply()ed once (see header note)
    NpuReArmState rearm_;
    NpuLifecycleState lifecycle_;     // M22 explicit device-lifecycle state machine

    // M22 reused temporaries (reserved/resized once; no per-frame realloc).
    std::vector<icraft::xrt::Tensor> inputs_;
    std::vector<char> read_buf_;
};

}  // namespace chain
