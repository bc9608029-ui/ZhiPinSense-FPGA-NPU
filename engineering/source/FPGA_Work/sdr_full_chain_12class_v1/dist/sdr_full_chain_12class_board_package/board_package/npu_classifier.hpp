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
// Lifecycle matches npu_only_smoke (8-class reference): the Device and Network
// are created exactly once; every inference runs in a FRESH Session with a FRESH
// input tensor, which avoids the observed fixed one-frame-delay artifact of a
// reused session.

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

namespace chain {

constexpr const char* kNpuDeviceUrl =
    "axi://zg330aiu?npu=0x40000000&dma=0x80000000";
constexpr std::chrono::milliseconds kNpuReadyTimeout{10000};
constexpr std::size_t kLogitsCount = 12;

class NpuClassifier12 {
public:
    // The Network is created and its contract checked BEFORE the device is
    // opened, so any malformed-model error leaks no device handle.
    explicit NpuClassifier12(const std::string& model_json,
                             const std::string& model_raw)
        : network_(icraft::xir::Network::CreateFromJsonFile(model_json)) {
        network_.lazyLoadParamsFromFile(model_raw);
        if (network_.inputs().size() != 1 || network_.outputs().size() != 1)
            throw std::runtime_error(
                "twelve-class network must have exactly one input and one output");
        check_input_contract();
        check_output_contract();
        device_ = icraft::xrt::Device::Open(kNpuDeviceUrl);
        open_ = true;
    }

    ~NpuClassifier12() {
        if (open_) icraft::xrt::Device::Close(device_);
    }

    NpuClassifier12(const NpuClassifier12&) = delete;
    NpuClassifier12& operator=(const NpuClassifier12&) = delete;

    // One inference.  `tensor` must hold kTensorFloats floats: the [2,1024]
    // model input in C-order (first 1024 = I, next 1024 = Q).  Returns 12 fp32
    // logits.  Throws on any contract or runtime failure (never a silent
    // HostBackend fallback -- the model is @zhuget(330)).
    std::vector<float> infer(const float* tensor) {
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

        auto input_tensor =
            icraft::xrt::Tensor(input_value).mallocOn(icraft::xrt::HostDevice::MemRegion());
        input_tensor.write(0,
                           const_cast<char*>(reinterpret_cast<const char*>(tensor)),
                           byte_count);

        // FRESH session + FRESH tensors per frame (see header note).
        std::vector<icraft::xrt::Tensor> inputs;
        inputs.reserve(1);
        inputs.push_back(std::move(input_tensor));
        auto session = icraft::xrt::Session::Create<
            icraft::xrt::zg330::ZG330Backend, icraft::xrt::HostBackend>(
            network_, { device_, icraft::xrt::HostDevice::Default() });
        session.apply();

        const auto outputs = session.forward(inputs);
        if (outputs.size() != 1)
            throw std::runtime_error("unexpected output count from NPU session");
        if (!outputs[0].waitForReady(kNpuReadyTimeout))
            throw std::runtime_error(
                "NPU inference did not become ready within timeout");
        return read_logits(outputs[0]);
    }

private:
    static std::vector<int64_t> shape_of(const icraft::xir::Value& value) {
        std::vector<int64_t> s;
        for (const auto dim : value.tensorType()->shape) s.push_back(dim);
        return s;
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

    static std::vector<float> read_logits(const icraft::xrt::Tensor& tensor) {
        const auto dtype = tensor.dtype();
        std::vector<char> bytes(dtype.bytes());
        auto host = tensor.to(icraft::xrt::HostDevice::MemRegion());
        host.read(bytes.data(), 0, bytes.size());
        if (bytes.size() != kLogitsCount * sizeof(float))
            throw std::runtime_error("unexpected logits size; expected 12 x FP32");
        std::vector<float> logits(kLogitsCount);
        std::memcpy(logits.data(), bytes.data(), bytes.size());
        return logits;
    }

    icraft::xrt::Device device_;
    bool open_ = false;
    icraft::xir::Network network_;
};

}  // namespace chain
