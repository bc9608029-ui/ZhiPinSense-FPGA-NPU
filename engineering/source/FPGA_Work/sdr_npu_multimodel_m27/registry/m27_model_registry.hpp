// M27 model registry (spec §八): slots A..E, each binding the 15 model fields,
// SHA-bound, loaded once at startup only (never per-frame).  Single-model residency
// (audit: MULTI_MODEL_RESIDENCY_UNSUPPORTED) is enforced by the NPU backend stub, not
// by this registry: the registry only decides *which* one model to load and validates
// its SHA against the binding.  header-only, namespace m27.
#ifndef M27_MODEL_REGISTRY_HPP
#define M27_MODEL_REGISTRY_HPP

#include <cstdint>
#include <string>
#include <vector>
#include "m27_contract.hpp"
#include "m27_npu_backend_stub.hpp"

namespace m27 {

class ModelRegistry {
 public:
  ModelRegistry() { init_default_slots(); }

  // Access a slot (mutable for construction-time binding only).
  ModelSlot& slot(SlotId s) { return slots_[static_cast<int>(s)]; }
  const ModelSlot& slot(SlotId s) const { return slots_[static_cast<int>(s)]; }

  // Validate the whole registry: every enabled, non-experimental slot must carry a
  // valid 64-hex model_sha256 (stubs may be empty because they are disabled), and
  // slot A (production) must match the frozen 12-class SHA and 12 labels.
  bool validate(std::string* why = nullptr) const {
    for (int i = 0; i < kMaxSlots; ++i) {
      const ModelSlot& m = slots_[i];
      if (m.enabled && !m.experimental && !sha256_valid(m.model_sha256)) {
        if (why) *why = std::string("slot ") + slot_name(static_cast<SlotId>(i)) +
                        " enabled but model_sha256 not a valid 64-hex value";
        return false;
      }
    }
    const ModelSlot& a = slots_[static_cast<int>(SlotId::A)];
    if (a.model_sha256 != kFrozen12ClassSha256) {
      if (why) *why = "slot A model_sha256 does not match frozen 12-class SHA";
      return false;
    }
    if (static_cast<int>(a.label_order.size()) != kClassCount12) {
      if (why) *why = "slot A label_order must be exactly 12 classes";
      return false;
    }
    return true;
  }

  // Choose and load the single resident model into the backend.
  //   - the first enabled slot wins (priority order == slot order for the stub);
  //   - a SHA mismatch with the binding fails closed (returns SHA_MISMATCH);
  //   - loading is performed exactly once at startup.
  NpuStatus load_resident(NpuBackendStub& backend) const {
    for (int i = 0; i < kMaxSlots; ++i) {
      const ModelSlot& m = slots_[i];
      if (!m.enabled) continue;
      NpuStatus st = backend.load(m, m.model_sha256);
      if (st != NpuStatus::OK) return st;
      loaded_slot_ = static_cast<SlotId>(i);
      return NpuStatus::OK;
    }
    return NpuStatus::NOT_LOADED;
  }

  SlotId loaded_slot() const { return loaded_slot_; }

 private:
  void init_default_slots() {
    // ---- slot A: current 12-class production model (enabled, frozen) ----
    ModelSlot& a = slots_[0];
    a.model_name = "12class_production";
    a.model_role = "production_12class";
    a.model_sha256 = kFrozen12ClassSha256;
    a.compiled_model_sha256 = "51364bdf000000000000000000000000000000000000000000000000000000";
    a.label_order = {"OOK", "4ASK", "AM-DSB", "WBFM", "2FSK", "GFSK",
                     "BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "OFDM"};
    a.input_contract = "[1,2,1024] planar IQ, RMS~1, no normalization";
    a.output_contract = "12 x float32 raw logits";
    a.numeric_type = "fp32";
    a.scale = 1.0f; a.zero_point = 0;
    a.memory_requirement = 2851472;
    a.priority = 0; a.enabled = true; a.experimental = false;
    a.timeout_ms = 1000; a.fallback_model = SlotId::A;

    // ---- slot B: 24-class model stub (disabled, not frozen) ----
    ModelSlot& b = slots_[1];
    b.model_name = "24class_stub";
    b.model_role = "24class_stub";
    b.model_sha256.clear();
    b.compiled_model_sha256.clear();
    b.input_contract = "[1,2,1024] planar IQ, RMS~1";
    b.output_contract = "24 x float32 raw logits";
    b.numeric_type = "fp32"; b.scale = 1.0f; b.zero_point = 0;
    b.memory_requirement = 0;
    b.priority = 1; b.enabled = false; b.experimental = true;
    b.timeout_ms = 1000; b.fallback_model = SlotId::A;

    // ---- slot C: confusable-class expert stub (disabled) ----
    ModelSlot& c = slots_[2];
    c.model_name = "expert_stub";
    c.model_role = "expert_stub";
    c.model_sha256.clear();
    c.compiled_model_sha256.clear();
    c.input_contract = "[1,2,1024] planar IQ, RMS~1";
    c.output_contract = "expert-class raw logits (unfrozen)";
    c.numeric_type = "fp32"; c.scale = 1.0f; c.zero_point = 0;
    c.memory_requirement = 0;
    c.priority = 2; c.enabled = false; c.experimental = true;
    c.timeout_ms = 1000; c.fallback_model = SlotId::A;

    // ---- slot D: channel/interference recognition prototype (experimental) ----
    ModelSlot& d = slots_[3];
    d.model_name = "channel_impairment_proto";
    d.model_role = "channel_impairment_prototype";
    d.model_sha256.clear();   // synthetic prototype, not a frozen production model
    d.compiled_model_sha256.clear();
    d.label_order = {"CLEAN", "CFO", "PHASE_NOISE", "IQ_IMBALANCE", "MULTIPATH",
                     "CLIPPING", "CW_INTERFERENCE", "MULTITONE", "PULSE", "SWEEP",
                     "MULTI_IMPAIRMENT"};
    d.input_contract = "[N,2,1024] planar IQ, RMS~1";
    d.output_contract = "11 x float32 raw logits (channel/environment)";
    d.numeric_type = "fp32"; d.scale = 1.0f; d.zero_point = 0;
    d.memory_requirement = 0;
    d.priority = 3; d.enabled = false; d.experimental = true;
    d.timeout_ms = 1000; d.fallback_model = SlotId::A;

    // ---- slot E: future OOD neural model stub (disabled) ----
    ModelSlot& e = slots_[4];
    e.model_name = "ood_neural_stub";
    e.model_role = "ood_neural_stub";
    e.model_sha256.clear();
    e.compiled_model_sha256.clear();
    e.input_contract = "[1,2,1024] planar IQ, RMS~1";
    e.output_contract = "OOD score (unfrozen)";
    e.numeric_type = "fp32"; e.scale = 1.0f; e.zero_point = 0;
    e.memory_requirement = 0;
    e.priority = 4; e.enabled = false; e.experimental = true;
    e.timeout_ms = 1000; e.fallback_model = SlotId::A;
  }

  ModelSlot slots_[kMaxSlots];
  mutable SlotId loaded_slot_ = SlotId::A;
};

}  // namespace m27

#endif  // M27_MODEL_REGISTRY_HPP
