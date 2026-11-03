#pragma once

#include <utility>

namespace icraft::osal::lifetime {

template <class T, class Tag, class Factory>
T& persistent(Factory&& factory) {
    static T* instance = nullptr;
    if (instance == nullptr) {
        instance = new T(std::forward<Factory>(factory)());
    }
    return *instance;
}

}  // namespace icraft::osal::lifetime
