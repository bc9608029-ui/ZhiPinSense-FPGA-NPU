#include <icraft-xrt/core/session.h>
#include <icraft-xrt/dev/zg330_device.h>

#include <cstdint>
#include <iomanip>
#include <iostream>

using icraft::xrt::Device;
using icraft::xrt::ZG330Device;

int main() {
    constexpr std::uint64_t kOfficialUserRegVersion = 0x400c00c0ULL;
    const char *device_url = "axi://zg330aiu?npu=0x40000000&dma=0x80000000";

    std::cout << "OPEN_BEGIN" << std::endl;
    auto device = Device::Open(device_url);
    auto fpai_device = device.cast<ZG330Device>();
    std::cout << "READ_BEGIN addr=0x" << std::hex << kOfficialUserRegVersion
              << std::dec << std::endl;
    const auto version = static_cast<std::uint32_t>(
        fpai_device.defaultRegRegion().read(kOfficialUserRegVersion, false));
    std::cout << "READ_PASS value=0x" << std::hex << std::setw(8)
              << std::setfill('0') << version << std::dec << std::endl;
    Device::Close(device);
    return 0;
}
