// M27 common contract — types, enums, frozen constants shared by the registry,
// router, buffer pool and temporal-fusion modules.
//
// This is a CPU-side host framework (offline).  It never touches the ZG330 runtime
// directly: the NPU backend is a single-model stub (m27_npu_backend_stub.hpp) that
// models the runtime capability audited in docs/M27_NPU_RUNTIME_CAPABILITY_AUDIT.md
// (MULTI_MODEL_RESIDENCY_UNSUPPORTED).  namespace m27, header-only.
#ifndef M27_CONTRACT_HPP
#define M27_CONTRACT_HPP

#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace m27 {

// Frozen 12-class production model SHA256 (MUST NOT change; spec §一).
constexpr const char* kFrozen12ClassSha256 =
    "2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c";

constexpr int kClassCount12 = 12;   // slot A: current production 12-class model
constexpr int kClassCount24 = 24;   // slot B: 24-class stub (not frozen)
constexpr int kMaxSlots      = 5;   // slots A..E
constexpr int kMaxLogits     = 24;  // largest supported class count (12/24)

// ---- presence state: strictly distinguished, never conflated ----
enum class PresenceState : int {
  NO_SIGNAL       = 0,
  SIGNAL_PRESENT  = 1,
  UNKNOWN         = 2   // OOD-U already rejected this frame: fusion must not override
};

// ---- model slots A..E (spec §八) ----
enum class SlotId : int {
  A = 0,   // current 12-class production model (enabled, frozen SHA)
  B = 1,   // 24-class model stub (disabled)
  C = 2,   // confusable-class expert model stub (disabled)
  D = 3,   // channel/interference recognition prototype (experimental)
  E = 4,   // future OOD neural model stub (disabled)
  SLOT_COUNT = 5
};

inline const char* slot_name(SlotId s) {
  switch (s) {
    case SlotId::A: return "A"; case SlotId::B: return "B";
    case SlotId::C: return "C"; case SlotId::D: return "D";
    case SlotId::E: return "E";
    default: return "?";
  }
}

// A SHA256 is exactly 64 lowercase hex chars (empty string = "not yet frozen").
inline bool sha256_valid(const std::string& s) {
  if (s.size() != 64) return false;
  for (char c : s) {
    bool ok = (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
    if (!ok) return false;
  }
  return true;
}

// ---- one registry entry: the 15 bound fields of spec §八 ----
struct ModelSlot {
  std::string model_name;             // 1
  std::string model_role;             // 2  e.g. "production_12class" / "24class_stub"
  std::string model_sha256;           // 3  64-hex (empty => stub, not frozen)
  std::string compiled_model_sha256;  // 4  compiled .raw/.onnx SHA
  std::vector<std::string> label_order;// 5 frozen label order
  std::string input_contract;         // 6  e.g. "[1,2,1024] planar IQ, RMS~1"
  std::string output_contract;        // 7  e.g. "12 x float32 raw logits"
  std::string numeric_type;           // 8  "fp32" / "int8"
  float       scale;                  // 9  quantization scale (1.0 for fp32)
  int         zero_point;             // 9  quantization zero-point (0 for fp32)
  std::uint64_t memory_requirement;   // 10 bytes
  int         priority;               // 11 lower = higher priority (0 = production)
  bool        enabled;                // 12 loaded only if true
  bool        experimental;           // 13 experimental model must not break production
  std::uint32_t timeout_ms;           // 14 inference timeout
  SlotId      fallback_model;         // 15 fallback slot on failure (A => A)
};

// ---- generic fusion input (spec §十), dimension-agnostic ----
struct FusionInput {
  std::uint64_t frame_id;
  std::uint64_t timestamp_ns;
  PresenceState presence;
  int           n;                     // class count: 12 or 24 (fail-closed on mismatch)
  const float*  raw_logits;            // [n]
  const float*  probabilities;         // [n] (may be null)
  float         ood_score;
  float         snr;
  float         signal_power;
  const char*   model_sha;             // 64-hex or nullptr; fusion never crosses SHA
};

// ---- routing input (spec §九) ----
struct RouteInput {
  int           n;                     // class count
  const float*  raw_logits;            // [n]
  float         margin;                // top1 - top2 (logit domain)
  float         entropy;               // softmax entropy
  float         ood_score;             // independent OOD score
  bool          impairment_severe;     // channel model flagged severe impairment
  bool          error;                 // NPU error this frame
  int           stable_frames;         // consecutive stable top-1 count
};

enum class RouteAction : int {
  DIRECT = 0,   // primary high-margin -> output directly
  EXPERT = 1,   // low margin / high entropy -> confusable-class expert (slot C stub)
  OOD    = 2,   // suspected unknown -> OOD (slot E stub) or CPU OOD score
  CHANNEL = 3,  // severe impairment -> channel/interference model (slot D)
  ERROR  = 4    // fail-closed: fall back to primary passthrough
};

struct RouteDecision {
  RouteAction action;
  const char* reason;   // static string literal
};

}  // namespace m27

#endif  // M27_CONTRACT_HPP
