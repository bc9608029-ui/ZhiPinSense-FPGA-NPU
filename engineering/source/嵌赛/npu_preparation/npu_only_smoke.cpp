#include <icraft-backends/zg330backend/zg330backend.h>
#include <icraft-xir/core/network.h>
#include <icraft-xrt/core/device.h>
#include <icraft-xrt/core/session.h>
#include <icraft-xrt/core/tensor.h>
#include <icraft-xrt/dev/host_device.h>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr std::size_t kFrameLength = 1024;
constexpr std::size_t kIqBytes = 2 * kFrameLength;
constexpr std::size_t kPhysicalBytes = 3 * kFrameLength;
constexpr std::size_t kFrameBytes = kIqBytes + kPhysicalBytes;
constexpr const char* kDeviceUrl = "axi://zg330aiu?npu=0x40000000&dma=0x80000000";

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

bool same_shape(const std::vector<int64_t>& actual, std::initializer_list<int64_t> expected) {
    return actual == std::vector<int64_t>(expected);
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

    const auto scale = dtype.getScale();
    if (scale.has_value()) {
        std::cout << " scales=[";
        const auto values = scale.value();
        for (std::size_t i = 0; i < values.size(); ++i) {
            if (i) std::cout << ',';
            std::cout << std::setprecision(10) << values[i]->origin_scale;
        }
        std::cout << ']';
    } else {
        std::cout << " scales=<none>";
    }

    const auto zero_points = dtype.getZeroPoints();
    if (zero_points.has_value()) {
        std::cout << " zero_points=[";
        const auto values = zero_points.value();
        for (std::size_t i = 0; i < values.size(); ++i) {
            if (i) std::cout << ',';
            std::cout << values[i];
        }
        std::cout << ']';
    } else {
        std::cout << " zero_points=<none>";
    }
    std::cout << '\n';
}

icraft::xrt::Tensor make_ncl_sint8_tensor(
    const icraft::xir::Value& value,
    const char* source,
    std::size_t byte_count) {
    const auto dtype = value.tensorType();
    const auto storage = dtype->element_dtype.getStorageType();
    if (!storage.isSInt8()) throw std::runtime_error("compiled input storage is not signed INT8");
    if (dtype->layout.toString() != "NCL") {
        throw std::runtime_error("compiled input physical layout is not NCL; explicit repacking is required");
    }
    if (dtype.bytes() != byte_count) {
        throw std::runtime_error("compiled input byte size is padded or otherwise differs from contiguous NCL");
    }
    auto tensor = icraft::xrt::Tensor(value).mallocOn(icraft::xrt::HostDevice::MemRegion());
    tensor.write(0, const_cast<char*>(source), byte_count);
    return tensor;
}

void print_argmax(const icraft::xrt::Tensor& tensor) {
    const auto dtype = tensor.dtype();
    const auto storage = dtype->element_dtype.getStorageType();
    auto host = tensor.to(icraft::xrt::HostDevice::MemRegion());
    std::vector<char> bytes(dtype.bytes());
    host.read(bytes.data(), 0, bytes.size());

    std::size_t best = 0;
    if (storage.isFP32() && bytes.size() == 8 * sizeof(float)) {
        std::vector<float> logits(8);
        std::memcpy(logits.data(), bytes.data(), bytes.size());
        best = static_cast<std::size_t>(std::distance(logits.begin(), std::max_element(logits.begin(), logits.end())));
    } else if (storage.isSInt8() && bytes.size() == 8) {
        const auto* logits = reinterpret_cast<const int8_t*>(bytes.data());
        best = static_cast<std::size_t>(std::distance(logits, std::max_element(logits, logits + 8)));
    } else {
        throw std::runtime_error("unsupported logits storage/size in smoke program");
    }
    static const char* classes[8] = {"BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"};
    std::cout << "argmax=" << best << " class=" << classes[best] << '\n';
}
}  // namespace

int main(int argc, char** argv) {
    if (argc < 4 || argc > 5) {
        std::cerr << "usage: " << argv[0] << " model.json model.raw tensor_5plane.bin [frame_index]\n";
        return 2;
    }

    try {
        const std::size_t frame_index = argc == 5 ? std::stoul(argv[4]) : 0;
        const auto payload = read_binary(argv[3]);
        if (payload.empty() || payload.size() % kFrameBytes != 0) {
            throw std::runtime_error("Tensor file size must be a non-zero multiple of 5120 bytes");
        }
        if (frame_index >= payload.size() / kFrameBytes) throw std::runtime_error("frame_index is out of range");
        const char* frame = payload.data() + frame_index * kFrameBytes;

        auto network = icraft::xir::Network::CreateFromJsonFile(argv[1]);
        network.lazyLoadParamsFromFile(argv[2]);
        if (network.inputs().size() != 2 || network.outputs().size() != 1) {
            throw std::runtime_error("compiled network must have exactly two inputs and one output");
        }

        std::vector<icraft::xrt::Tensor> inputs;
        inputs.reserve(2);
        for (std::size_t i = 0; i < network.inputs().size(); ++i) {
            const auto value = network.inputs()[i];
            print_value_contract("input", i, value);
            const auto shape = shape_of(value);
            if (same_shape(shape, {1, 2, 1024})) {
                inputs.push_back(make_ncl_sint8_tensor(value, frame, kIqBytes));
            } else if (same_shape(shape, {1, 3, 1024})) {
                inputs.push_back(make_ncl_sint8_tensor(value, frame + kIqBytes, kPhysicalBytes));
            } else {
                throw std::runtime_error("unexpected compiled input shape");
            }
        }
        print_value_contract("output", 0, network.outputs()[0]);

        auto device = icraft::xrt::Device::Open(kDeviceUrl);
        // Intentionally no HostBackend: unsupported/fallback operations must fail.
        auto session = icraft::xrt::Session::Create<icraft::xrt::zg330::ZG330Backend>(network, {device});
        session.apply();
        const auto outputs = session.forward(inputs);
        if (outputs.size() != 1 || !outputs[0].waitForReady(std::chrono::milliseconds(10000))) {
            icraft::xrt::Device::Close(device);
            throw std::runtime_error("NPU inference timeout or unexpected output count");
        }
        print_argmax(outputs[0]);
        icraft::xrt::Device::Close(device);
        std::cout << "V2_NPU_ONLY_SMOKE_PASS\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "V2_NPU_ONLY_SMOKE_FAIL: " << error.what() << '\n';
        return 1;
    }
}
