#pragma once

#include "icraft-utils/osal/sync.hpp"

namespace icraft::midware {

using Mutex = icraft::osal::sync::Mutex;

template <class MutexType>
using LockGuard = icraft::osal::sync::LockGuard<MutexType>;

}  // namespace icraft::midware