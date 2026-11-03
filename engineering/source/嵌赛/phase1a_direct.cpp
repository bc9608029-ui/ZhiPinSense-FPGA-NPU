#include <cerrno>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

namespace {
constexpr std::uint64_t kFrameCtrlBase = 0x40080000ULL;
constexpr std::size_t kMapBytes = 0x1000;
constexpr std::size_t kVersionOffset = 0x0c;
constexpr std::size_t kReadAddressOffset = 0x54;
constexpr std::uint32_t kExpectedVersion = 0x20230218U;
constexpr int kWidth = 1280;
constexpr int kHeight = 720;
constexpr std::size_t kFrameBytes = static_cast<std::size_t>(kWidth) * kHeight * 2;

struct Mapping {
    int fd = -1;
    void* address = MAP_FAILED;
    std::size_t length = 0;
    ~Mapping() {
        if (address != MAP_FAILED) munmap(address, length);
        if (fd >= 0) close(fd);
    }
};

std::uint64_t read_number(const char* path) {
    std::ifstream input(path);
    std::string value;
    if (!(input >> value)) throw std::runtime_error(std::string("cannot read ") + path);
    return std::stoull(value, nullptr, 0);
}

void sync_for_device_if_available() {
    const char* path = "/sys/class/u-dma-buf/udmabuf0/sync_for_device";
    std::ofstream output(path);
    if (output) {
        output << "1";
        output.flush();
        std::cout << "[1A-DIRECT] sync_for_device requested\n";
    } else {
        std::cout << "[1A-DIRECT] sync_for_device node absent; using O_SYNC + msync\n";
    }
}

std::uint16_t rgb565(std::uint8_t r, std::uint8_t g, std::uint8_t b) {
    return static_cast<std::uint16_t>(((r & 0xf8U) << 8U) |
                                      ((g & 0xfcU) << 3U) |
                                      (b >> 3U));
}

void fill_checker(std::uint16_t* pixels) {
    const auto dark = rgb565(0x20, 0x20, 0x20);
    const auto light = rgb565(0xe0, 0xe0, 0xe0);
    const auto white = rgb565(0xff, 0xff, 0xff);
    for (int y = 0; y < kHeight; ++y) {
        for (int x = 0; x < kWidth; ++x) {
            auto color = (((x / 32) + (y / 32)) & 1) ? light : dark;
            if (x < 4 || x >= kWidth - 4 || y < 4 || y >= kHeight - 4) color = white;
            pixels[static_cast<std::size_t>(y) * kWidth + x] = color;
        }
    }
}
}

int main() try {
    const char* dev_path = "/dev/udmabuf0";
    const char* sysfs_base = "/sys/class/u-dma-buf/udmabuf0/";
    const auto physical = read_number((std::string(sysfs_base) + "phys_addr").c_str());
    const auto capacity = read_number((std::string(sysfs_base) + "size").c_str());

    std::cout << "[1A-DIRECT] udmabuf0 phys=0x" << std::hex << physical << std::dec
              << " size=" << capacity << " frame_bytes=" << kFrameBytes << "\n";
    if ((physical & 7U) != 0 || physical >= (1ULL << 30) || capacity < kFrameBytes) {
        std::cerr << "[1A-DIRECT] FAIL: invalid framebuffer address/alignment/capacity\n";
        return 2;
    }

    Mapping framebuffer;
    framebuffer.fd = open(dev_path, O_RDWR | O_SYNC);
    if (framebuffer.fd < 0) throw std::runtime_error(std::string("open udmabuf0: ") + std::strerror(errno));
    framebuffer.length = kFrameBytes;
    framebuffer.address = mmap(nullptr, framebuffer.length, PROT_READ | PROT_WRITE,
                               MAP_SHARED, framebuffer.fd, 0);
    if (framebuffer.address == MAP_FAILED)
        throw std::runtime_error(std::string("mmap udmabuf0: ") + std::strerror(errno));

    fill_checker(static_cast<std::uint16_t*>(framebuffer.address));
    if (msync(framebuffer.address, framebuffer.length, MS_SYNC) != 0) {
        if (errno != EINVAL)
            throw std::runtime_error(std::string("msync udmabuf0: ") + std::strerror(errno));
        std::cout << "[1A-DIRECT] msync unsupported by udmabuf0; using driver sync node\n";
    }
    sync_for_device_if_available();

    Mapping registers;
    registers.fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (registers.fd < 0) throw std::runtime_error(std::string("open /dev/mem: ") + std::strerror(errno));
    registers.length = kMapBytes;
    registers.address = mmap(nullptr, registers.length, PROT_READ | PROT_WRITE,
                             MAP_SHARED, registers.fd, static_cast<off_t>(kFrameCtrlBase));
    if (registers.address == MAP_FAILED)
        throw std::runtime_error(std::string("mmap frame_ctrl: ") + std::strerror(errno));

    auto* words = static_cast<volatile std::uint32_t*>(registers.address);
    const auto version = words[kVersionOffset / 4];
    std::cout << "[1A-DIRECT] frame_ctrl version=0x" << std::hex << std::setw(8)
              << std::setfill('0') << version << std::dec << "\n";
    if (version != kExpectedVersion) {
        std::cerr << "[1A-DIRECT] FAIL: version mismatch; register write refused\n";
        return 3;
    }

    const auto shifted = static_cast<std::uint32_t>(physical >> 3U);
    words[kReadAddressOffset / 4] = shifted;
    __sync_synchronize();
    const auto readback = words[kReadAddressOffset / 4];
    std::cout << "[1A-DIRECT] wrote/read 0x40080054=0x" << std::hex << shifted
              << "/0x" << readback << std::dec << "\n";
    if (readback != shifted) {
        std::cerr << "[1A-DIRECT] FAIL: register readback mismatch\n";
        return 4;
    }

    std::cout << "PHASE1A_PS_PASS_DIRECT checker 1280x720 RGB565\n";
    std::cout << "Press Enter only after the visual check.\n";
    std::string line;
    std::getline(std::cin, line);
    return 0;
} catch (const std::exception& error) {
    std::cerr << "[1A-DIRECT] FAIL: " << error.what() << "\n";
    return 1;
}
