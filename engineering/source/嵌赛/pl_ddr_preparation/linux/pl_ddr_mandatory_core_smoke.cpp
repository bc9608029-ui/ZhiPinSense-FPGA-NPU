#include <icraft-xrt/core/session.h>
#include <icraft-xrt/dev/zg330_device.h>

#include <chrono>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include "pl_ddr_register_map.hpp"

using icraft::xrt::Device;
using icraft::xrt::ZG330Device;

namespace {
constexpr std::size_t kFrameCount = 19;
constexpr std::size_t kFrameLength = 1024;
constexpr std::size_t kIqBytes = kFrameCount * kFrameLength * 4;
constexpr std::size_t kTensorFrameBytes = 5 * kFrameLength;
constexpr std::size_t kTensorBytes = kFrameCount * kTensorFrameBytes;
constexpr std::size_t kIqOffset = 0;
constexpr std::size_t kTensorOffset = kIqBytes;
constexpr std::size_t kAllocationBytes = kIqBytes + kTensorBytes;

std::uint64_t parse_u64(const char* text) {
    std::size_t consumed = 0;
    const auto value = std::stoull(text, &consumed, 0);
    if (text[consumed] != '\0') {
        throw std::invalid_argument(std::string("invalid integer: ") + text);
    }
    return value;
}

std::vector<char> read_exact(const std::string& path, std::size_t expected_size) {
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    if (!stream) {
        throw std::runtime_error("cannot open input file: " + path);
    }
    const auto size = static_cast<std::size_t>(stream.tellg());
    if (size != expected_size) {
        throw std::runtime_error(
            "input size is " + std::to_string(size) +
            ", expected " + std::to_string(expected_size));
    }
    stream.seekg(0);
    std::vector<char> data(size);
    stream.read(data.data(), static_cast<std::streamsize>(size));
    if (!stream) {
        throw std::runtime_error("failed to read input file: " + path);
    }
    return data;
}

void write_all(const std::string& path, const std::vector<char>& data) {
    std::ofstream stream(path, std::ios::binary);
    if (!stream) {
        throw std::runtime_error("cannot open output file: " + path);
    }
    stream.write(data.data(), static_cast<std::streamsize>(data.size()));
    if (!stream) {
        throw std::runtime_error("failed to write output file: " + path);
    }
}
}  // namespace

int main(int argc, char** argv) {
    if (argc != 5) {
        std::cerr
            << "usage: " << argv[0]
            << " <device-url> <verified-reg-base> <iq_input.bin> <tensor_output.bin>\n";
        return 2;
    }

    Device device;
    try {
        const std::string device_url = argv[1];
        const std::uint64_t reg_base = parse_u64(argv[2]);
        if (reg_base > 0xffff'ffffULL || (reg_base & 3u) != 0) {
            throw std::invalid_argument("register base must be an aligned 32-bit address");
        }
        auto iq = read_exact(argv[3], kIqBytes);

        device = Device::Open(device_url);
        auto fpai_device = device.cast<ZG330Device>();
        auto& regs = fpai_device.defaultRegRegion();

        // This follows the official adder_demo MemChunk allocation and access
        // pattern.  No /dev/mem mapping or separately invented DMA is used.
        auto chunk = fpai_device.defaultMemRegion().malloc(kAllocationBytes, false, 64);
        const std::uint64_t chunk_addr = chunk->begin.addr();
        const std::uint64_t tensor_addr = chunk_addr + kTensorOffset;
        if (chunk_addr > 0xffff'ffffULL || tensor_addr > 0xffff'ffffULL) {
            throw std::runtime_error("allocated PL-DDR address does not fit User_Ddr_*[31:0]");
        }
        if ((chunk_addr & 63u) != 0 || (tensor_addr & 63u) != 0) {
            throw std::runtime_error("runtime returned a non-64-byte-aligned MemChunk");
        }

        std::vector<char> zeros(kTensorBytes, 0);
        chunk.write(kIqOffset, iq.data(), iq.size());
        chunk.write(kTensorOffset, zeros.data(), zeros.size());

        const auto write_reg = [&](std::uint64_t offset, std::uint32_t value) {
            regs.write(reg_base + offset, value, false);
        };
        const auto read_reg = [&](std::uint64_t offset) {
            return static_cast<std::uint32_t>(regs.read(reg_base + offset, false));
        };

        write_reg(pl_ddr_regs::CONTROL, pl_ddr_regs::CONTROL_CLEAR);
        write_reg(pl_ddr_regs::IQ_BASE, static_cast<std::uint32_t>(chunk_addr));
        write_reg(pl_ddr_regs::IQ_BYTES, static_cast<std::uint32_t>(kIqBytes));
        write_reg(pl_ddr_regs::TENSOR_BASE, static_cast<std::uint32_t>(tensor_addr));
        write_reg(pl_ddr_regs::TENSOR_BYTES, static_cast<std::uint32_t>(kTensorBytes));
        write_reg(pl_ddr_regs::FRAME_COUNT, static_cast<std::uint32_t>(kFrameCount));
        write_reg(pl_ddr_regs::CONTROL, pl_ddr_regs::CONTROL_START);

        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
        std::uint32_t status = 0;
        while (std::chrono::steady_clock::now() < deadline) {
            status = read_reg(pl_ddr_regs::STATUS);
            if (status & (pl_ddr_regs::STATUS_DONE | pl_ddr_regs::STATUS_ERROR)) {
                break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        if ((status & pl_ddr_regs::STATUS_DONE) == 0) {
            throw std::runtime_error("timeout waiting for PL-DDR operation DONE");
        }
        if (status & pl_ddr_regs::STATUS_ERROR) {
            const auto code = read_reg(pl_ddr_regs::ERROR_CODE);
            throw std::runtime_error("PL-DDR operation reported error " + std::to_string(code));
        }

        const auto iq_accepted = read_reg(pl_ddr_regs::IQ_ACCEPTED);
        const auto tensor_accepted = read_reg(pl_ddr_regs::TENSOR_ACCEPTED);
        if (iq_accepted != kFrameCount * kFrameLength ||
            tensor_accepted != kFrameCount * kFrameLength) {
            throw std::runtime_error("accepted sample counters do not match 19x1024");
        }

        std::vector<char> tensor(kTensorBytes);
        chunk.read(tensor.data(), kTensorOffset, tensor.size());
        write_all(argv[4], tensor);

        std::cout << "PL_DDR_MANDATORY_CORE_LINUX_PASS"
                  << " chunk=0x" << std::hex << chunk_addr
                  << " tensor=0x" << tensor_addr << std::dec
                  << " iq_samples=" << iq_accepted
                  << " tensor_samples=" << tensor_accepted << '\n';
        Device::Close(device);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        if (device.defined()) {
            Device::Close(device);
        }
        return 1;
    }
}
