#include <icraft-xrt/core/device.h>

#include <exception>
#include <iostream>

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: open_icraft_device URL\n";
        return 2;
    }
    try {
        std::cout << "OPEN_BEGIN " << argv[1] << std::endl;
        auto device = icraft::xrt::Device::Open(argv[1]);
        std::cout << "OPEN_PASS" << std::endl;
        icraft::xrt::Device::Close(device);
        std::cout << "CLOSE_PASS" << std::endl;
        return 0;
    }
    catch (const std::exception& error) {
        std::cerr << "OPEN_FAIL " << error.what() << std::endl;
        return 1;
    }
}
