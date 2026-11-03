#include <icraft-xrt/core/device.h>

#include <iostream>

int main() {
    for (const auto name : icraft::xrt::DeviceRegistry::ListNames()) {
        std::cout << name << '\n';
    }
    return 0;
}
