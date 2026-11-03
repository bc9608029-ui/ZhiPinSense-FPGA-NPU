#include <icraft-xrt/core/session.h>
#include <icraft-xrt/dev/zg330_device.h>

#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <thread>

using icraft::xrt::Device;
using icraft::xrt::ZG330Device;

namespace {
constexpr std::uint64_t kBase = 0x400c0000ULL;
constexpr std::uint64_t kVersion = 0x00;
constexpr std::uint64_t kScratch = 0x04;
constexpr std::uint64_t kControl = 0x08;
constexpr std::uint64_t kStatus = 0x0c;
constexpr std::uint64_t kRunCount = 0x10;
constexpr std::uint32_t kExpectedVersion = 0x20260927U;
constexpr std::uint32_t kScratchPattern = 0x12345678U;
}

int main() {
    const char *device_url = "axi://zg330aiu?npu=0x40000000&dma=0x80000000";
    auto device = Device::Open(device_url);
    auto fpai_device = device.cast<ZG330Device>();
    auto &regs = fpai_device.defaultRegRegion();

    const auto version = static_cast<std::uint32_t>(regs.read(kBase + kVersion, false));
    std::cout << "VERSION=0x" << std::hex << std::setw(8) << std::setfill('0')
              << version << std::dec << '\n';
    if (version != kExpectedVersion) {
        std::cerr << "FAIL: VERSION mismatch\n";
        Device::Close(device);
        return 1;
    }

    regs.write(kBase + kScratch, kScratchPattern, false);
    const auto scratch = static_cast<std::uint32_t>(regs.read(kBase + kScratch, false));
    std::cout << "SCRATCH=0x" << std::hex << std::setw(8) << std::setfill('0')
              << scratch << std::dec << '\n';
    if (scratch != kScratchPattern) {
        std::cerr << "FAIL: SCRATCH mismatch\n";
        Device::Close(device);
        return 2;
    }

    const auto before = static_cast<std::uint32_t>(regs.read(kBase + kRunCount, false));
    regs.write(kBase + kControl, 1U, false);

    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(1);
    std::uint32_t status = 0;
    do {
        status = static_cast<std::uint32_t>(regs.read(kBase + kStatus, false));
        if ((status & 0x2U) != 0U) break;
        std::this_thread::sleep_for(std::chrono::microseconds(50));
    } while (std::chrono::steady_clock::now() < deadline);

    const auto after = static_cast<std::uint32_t>(regs.read(kBase + kRunCount, false));
    std::cout << "STATUS=0x" << std::hex << status << std::dec
              << " RUN_COUNT_BEFORE=" << before
              << " RUN_COUNT_AFTER=" << after << '\n';

    Device::Close(device);
    if ((status & 0x2U) == 0U || (status & 0x1U) != 0U || after != before + 1U) {
        std::cerr << "FAIL: START/DONE/RUN_COUNT mismatch\n";
        return 3;
    }

    std::cout << "PS_PL_CTRL_SMOKE_LINUX_PASS\n";
    return 0;
}
