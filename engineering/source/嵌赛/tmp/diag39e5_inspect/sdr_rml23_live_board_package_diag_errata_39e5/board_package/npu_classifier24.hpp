#pragma once

// npu_classifier24.hpp — iCraft-only, single-input 24-class NPU inference
// wrapper (M29 Phase F5 RML23 live chain).  Board-only: builds on the FMQL30TAI
// Linux image against the iCraft 3.39 SDK (ZG330Backend + HostBackend); it is
// NOT compiled on the host (host tests cover chain_common.hpp + rml23_merged.hpp
// instead).
//
// This is the 24-class analogue of npu_classifier.hpp::NpuClassifier12.  The
// model is the frozen expA_bf16_head candidate (M29 Phase D.1/F):
//   input  iq     [1,2,1024] fp32  @hostt  (plane 0 = I, plane 1 = Q, C-order)
//   output logits [1,24]     fp32  @hostt  (raw logits, no softmax)
//   json SHA d43a2284… / raw SHA 2425d990… / target @zhuget(330)
//
// The 24->23 AM-SSB merge is NOT done here: this wrapper emits the raw 24-dim
// logits, and the caller feeds them to rml23::merge_logits_23 (rml23_merged.hpp)
// before publishing.  Lifecycle is identical to NpuClassifier12: Device opened
// once, one persistent Session create+apply()ed once, first frame forwards
// directly, every frame after gets exactly one Device::reset(1) before forward
// and never re-applies (see npu_rearm_state.hpp).

#include <icraft-backends/zg330backend/zg330backend.h>
#include <icraft-backends/hostbackend/backend.h>
#include <icraft-xir/core/network.h>
#include <icraft-xrt/core/device.h>
#include <icraft-xrt/core/session.h>
#include <icraft-xrt/core/tensor.h>
#include <icraft-xrt/dev/host_device.h>

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

#include "chain_common.hpp"
#include "npu_rearm_state.hpp"
#include "../sdr_adapter/npu_lifecycle_state.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/sha256.hpp"

namespace chain {

constexpr const char* kNpuDeviceUrl24 =
    "axi://zg330aiu?npu=0x40000000&dma=0x80000000";
constexpr std::chrono::milliseconds kNpuReadyTimeout24{10000};
constexpr std::size_t kLogitsCount24 = 24;

class NpuClassifier24 {
public:
    // Network created and contract checked BEFORE the device is opened, so a
    // malformed-model error leaks no device handle.  `timing` records the two
    // one-time bring-up stages (ModelLoad, DeviceOpen) for the runtime baseline.
    explicit NpuClassifier24(const std::string& model_json,
                             const std::string& model_raw,
                             m22::StageTiming* timing = nullptr)
        : network_(icraft::xir::Network::CreateFromJsonFile(model_json)) {
        const auto model_t0 = std::chrono::steady_clock::now();
        network_.lazyLoadParamsFromFile(model_raw);
        if (network_.inputs().size() != 1 || network_.outputs().size() != 1)
            throw std::runtime_error(
                "24-class network must have exactly one input and one output");
        check_input_contract();
        check_output_contract();
        if (timing)
            timing->record(m22::StageId::ModelLoad, elapsed_us(model_t0));

        const auto dev_t0 = std::chrono::steady_clock::now();
        device_ = icraft::xrt::Device::Open(kNpuDeviceUrl24);
        open_ = true;
        lifecycle_.record_open();

        // Persistent Session: created once, apply()ed once.  Re-applying after a
        // Device::reset(1) is a discipline violation; apply exactly once here.
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

        inputs_.reserve(1);   // reserve once so push_back never reallocates
    }

    ~NpuClassifier24() {
        lifecycle_.record_close();
        if (open_) icraft::xrt::Device::Close(device_);
    }

    NpuClassifier24(const NpuClassifier24&) = delete;
    NpuClassifier24& operator=(const NpuClassifier24&) = delete;

    // One inference.  `tensor` must hold kTensorFloats floats: the [2,1024]
    // model input in C-order (first 1024 = I, next 1024 = Q).  Returns 24 fp32
    // raw logits.  Throws on any contract or runtime failure.
    std::vector<float> infer(const float* tensor) {
        std::vector<float> logits;
        infer(tensor, logits);
        return logits;
    }

    // Allocation-reuse inference: writes 24 fp32 raw logits into `out`.  Reuses
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

        std::string src_sha;
        if (input_audit_)
            src_sha = audit_input(tensor, input_tensor, byte_count);

        inputs_.clear();
        inputs_.push_back(std::move(input_tensor));

        const bool need_reset = rearm_.begin_frame();
        bool reset_done = false;

        for (;;) {
            try {
                if (need_reset && !reset_done) {
                    device_.reset(1);   // "reset FPGA state only"
                    rearm_.record_reset(true);
                    reset_done = true;
                }
                const auto outputs = session_.forward(inputs_);
                if (outputs.size() != 1)
                    throw std::runtime_error("unexpected output count from NPU session");
                if (!outputs[0].waitForReady(kNpuReadyTimeout24))
                    throw std::runtime_error(
                        "NPU inference did not become ready within timeout");
                read_logits(outputs[0], out);
                if (input_audit_) {
                    // The backend must treat the host input as read-only: re-read
                    // it after forward and require byte-identity with the source.
                    std::vector<char> rb(byte_count);
                    inputs_[0].read(rb.data(), 0, byte_count);
                    if (sdr::Sha256::hex(rb.data(), byte_count) != src_sha)
                        throw std::runtime_error(
                            "input-transfer audit: host input modified by backend");
                }
                lifecycle_.record_frame_ok();
                return;
            } catch (...) {
                if (rearm_.reset_failed()) { lifecycle_.record_fatal(); throw; }
                if (!lifecycle_.record_frame_failure()) throw;
            }
        }
    }

    // Re-arm / session discipline counters.
    std::uint64_t reset_count() const { return rearm_.reset_count(); }
    std::uint64_t frame_count() const { return rearm_.frame_count(); }
    std::uint64_t apply_count() const { return rearm_.apply_count(); }
    bool reset_failed() const { return rearm_.reset_failed(); }
    bool discipline_ok() const { return rearm_.discipline_ok(); }

    // D-level input-transfer audit (errata 39e5 #2): when enabled, infer() proves
    // the source bytes, the mapped host destination and the post-forward host
    // input are all byte-identical (SHA-256), and logs the input geometry once.
    // Default off: no SHA, no read-back on the hot path.
    void set_input_audit(bool on) { input_audit_ = on; }
    bool input_audit() const { return input_audit_; }

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
        if (s.size() != 2 || s[0] != 1 || s[1] != static_cast<int64_t>(kLogitsCount24))
            throw std::runtime_error(
                "unexpected compiled output shape (expected [1,24])");
    }

    // Read the host raw 24-dim logits into `out`, reusing the member read buffer.
    void read_logits(const icraft::xrt::Tensor& tensor, std::vector<float>& out) {
        const auto dtype = tensor.dtype();
        read_buf_.resize(dtype.bytes());
        auto host = tensor.to(icraft::xrt::HostDevice::MemRegion());
        host.read(read_buf_.data(), 0, read_buf_.size());
        if (read_buf_.size() != kLogitsCount24 * sizeof(float))
            throw std::runtime_error("unexpected logits size; expected 24 x FP32");
        out.resize(kLogitsCount24);
        std::memcpy(out.data(), read_buf_.data(), read_buf_.size());
    }

    // D-level input-transfer audit (errata 39e5 #2).  The compiled input is
    // @hostt and this adapter allocates the input tensor on the HOST region
    // (HostDevice::MemRegion()), so the "mapped destination" is plain host
    // memory: the write is a host memcpy and there is no explicit msync/flush
    // step (the XRT public interface -- tensor.h / device.h -- exposes no sync
    // API; the device-side transfer + cache sync happens inside ZG330Backend's
    // Session::forward(), compiled SDK, not header-visible).  We prove the host
    // side byte-for-byte here and leave device-side sync correctness to the
    // three-backend comparison (Stage E).  Returns the source SHA for the
    // post-forward re-check.
    std::string audit_input(const float* tensor,
                            const icraft::xrt::Tensor& input_tensor,
                            std::size_t byte_count) {
        const std::string src_sha = sdr::Sha256::hex(tensor, byte_count);
        std::vector<char> rb(byte_count);
        input_tensor.read(rb.data(), 0, byte_count);
        if (sdr::Sha256::hex(rb.data(), byte_count) != src_sha)
            throw std::runtime_error(
                "input-transfer audit: mapped destination bytes != source bytes");
        if (!input_audit_logged_) {
            input_audit_logged_ = true;
            std::uint64_t align_mod64 = 0;
            try {
                align_mod64 = static_cast<std::uint64_t>(
                    reinterpret_cast<std::uintptr_t>(input_tensor.data().cptr())) % 64u;
            } catch (...) {
                align_mod64 = UINT64_MAX;  // ADDR-type MemPtr has no cptr()
            }
            std::printf(
                "NPU_INPUT_AUDIT byte_count=%zu shape=[1,2,1024] dtype=FP32 "
                "layout=contig-C-order plane0=I plane1=Q stride=[8192,4096,4] "
                "region=host alloc_align_mod64=%llu "
                "sync=host-memcpy+device-sync-in-forward\n",
                byte_count, static_cast<unsigned long long>(align_mod64));
            std::fflush(stdout);
        }
        return src_sha;
    }

    icraft::xrt::Device device_;
    bool open_ = false;
    icraft::xir::Network network_;
    icraft::xrt::Session session_;   // persistent, apply()ed once (see header note)
    NpuReArmState rearm_;
    NpuLifecycleState lifecycle_;

    std::vector<icraft::xrt::Tensor> inputs_;
    std::vector<char> read_buf_;
    bool input_audit_ = false;        // errata 39e5 #2: default off
    bool input_audit_logged_ = false; // geometry logged at most once
};

}  // namespace chain
