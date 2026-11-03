// M27 NPU backend stub (single-model residency).  Models the audited ZG330/iCraft
// 3.39 runtime capability: exactly one model may be loaded at a time, and loading a
// second model while another is resident returns MULTI_MODEL_RESIDENCY_UNSUPPORTED.
//
// The stub never performs real inference; `infer` copies the resident model's fixed
// class count through as a deterministic identity function so that routing/fusion
// integration can be exercised end to end without a board or a real NPU.  header-only,
// namespace m27.  Offline only.
#ifndef M27_NPU_BACKEND_STUB_HPP
#define M27_NPU_BACKEND_STUB_HPP

#include <cstdint>
#include <cstring>
#include <string>
#include "m27_contract.hpp"

namespace m27 {

enum class NpuStatus : int {
  OK = 0,
  MULTI_MODEL_RESIDENCY_UNSUPPORTED = 1,   // second model load rejected
  SHA_MISMATCH = 2,                        // model SHA does not match registry binding
  NOT_LOADED = 3,                          // infer before any load
  TIMEOUT = 4                              // simulated inference timeout
};

inline const char* npu_status_str(NpuStatus s) {
  switch (s) {
    case NpuStatus::OK: return "OK";
    case NpuStatus::MULTI_MODEL_RESIDENCY_UNSUPPORTED:
      return "MULTI_MODEL_RESIDENCY_UNSUPPORTED";
    case NpuStatus::SHA_MISMATCH: return "SHA_MISMATCH";
    case NpuStatus::NOT_LOADED: return "NOT_LOADED";
    case NpuStatus::TIMEOUT: return "TIMEOUT";
    default: return "?";
  }
}

class NpuBackendStub {
 public:
  // Load `model`.  Only one model is resident at a time; a load while another model
  // (different name) is already loaded is refused.  The model's SHA is checked against
  // `expected_sha` when the latter is non-empty and valid.
  NpuStatus load(const ModelSlot& model, const std::string& expected_sha) {
    if (loaded_ && resident_name_ != model.model_name) {
      return NpuStatus::MULTI_MODEL_RESIDENCY_UNSUPPORTED;
    }
    if (!expected_sha.empty() && sha256_valid(expected_sha)) {
      if (model.model_sha256 != expected_sha) return NpuStatus::SHA_MISMATCH;
    }
    resident_name_ = model.model_name;
    resident_n_ = static_cast<int>(model.label_order.size());
    resident_timeout_ms_ = model.timeout_ms;
    loaded_ = true;
    return NpuStatus::OK;
  }

  void unload() {
    loaded_ = false;
    resident_name_.clear();
    resident_n_ = 0;
  }

  bool loaded() const { return loaded_; }
  int resident_n() const { return resident_n_; }

  // Simulate one inference.  `timeout` models a slow/hung inference and returns
  // TIMEOUT.  Output is the deterministic identity pass-through (out[i] = in[i]) so
  // downstream fusion/routing see well-defined logits.  Returns false on any error.
  NpuStatus infer(const float* in, int n, float* out, bool timeout = false) {
    if (!loaded_) return NpuStatus::NOT_LOADED;
    if (n != resident_n_) return NpuStatus::NOT_LOADED;   // shape mismatch
    if (timeout) return NpuStatus::TIMEOUT;
    std::memcpy(out, in, static_cast<std::size_t>(n) * sizeof(float));
    return NpuStatus::OK;
  }

 private:
  bool loaded_ = false;
  std::string resident_name_;
  int resident_n_ = 0;
  std::uint32_t resident_timeout_ms_ = 0;
};

}  // namespace m27

#endif  // M27_NPU_BACKEND_STUB_HPP
