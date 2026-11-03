#pragma once

#include "icraft-xrt/core/tensor.h"

namespace icraft::xrt::utils {
    XRT_DLL icraft::xrt::Tensor Ftmp2Tensor(const std::string& ftmp_path, const xir::Value& value);
}