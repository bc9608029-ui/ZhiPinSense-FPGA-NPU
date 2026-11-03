// M27 conditional router (spec §九): a CPU-side scheduler that picks the inference
// path from the primary model's confidence signals.  All routing thresholds are
// *configuration*, documented to be fixed only by validation/calibration data — the
// defaults here are placeholders for offline integration, never a board claim.
// header-only, namespace m27.
#ifndef M27_CONDITIONAL_ROUTER_HPP
#define M27_CONDITIONAL_ROUTER_HPP

#include <cstdint>
#include "m27_contract.hpp"
#include "m27_runtime_stats.hpp"

namespace m27 {

struct RouterConfig {
  float margin_low = 1.0f;          // logit margin below which we distrust top-1
  float entropy_high = 1.8f;        // softmax entropy above which we distrust top-1
  float ood_suspect = 0.5f;         // OOD score above which -> OOD path
  int   stability_frames = 4;       // consecutive stable frames to suppress expert
  int   expert_min_interval = 8;    // min frames between expert calls once stable
};

class ConditionalRouter {
 public:
  void configure(const RouterConfig& c) { cfg_ = c; since_expert_ = 0; }

  // Route one frame.  Records per-slot calls and the (estimated) inference time of
  // the chosen action into `stats`.  `primary_us` is the measured primary latency.
  RouteDecision route(const RouteInput& in, RuntimeStats& stats,
                      std::uint32_t primary_us) {
    stats.windows_processed++;

    // NPU error -> fail-closed: passthrough primary, do not escalate.
    if (in.error) {
      stats.model[static_cast<int>(SlotId::A)].calls++;
      return {RouteAction::ERROR, "primary_error_fail_closed"};
    }

    bool high_margin = in.margin >= cfg_.margin_low;
    bool low_entropy = in.entropy <= cfg_.entropy_high;

    // High confidence and no other trigger -> direct.
    if (high_margin && low_entropy && !in.impairment_severe &&
        in.ood_score <= cfg_.ood_suspect) {
      stats.model[static_cast<int>(SlotId::A)].calls++;
      stats.model[static_cast<int>(SlotId::A)].inference_us_total += primary_us;
      stats.busy_us_total += primary_us;
      return {RouteAction::DIRECT, "high_margin_direct"};
    }

    // Severe channel impairment -> channel/interference model (slot D prototype).
    if (in.impairment_severe) {
      stats.model[static_cast<int>(SlotId::D)].calls++;
      return {RouteAction::CHANNEL, "severe_impairment"};
    }

    // Suspected unknown -> OOD path (slot E stub / CPU OOD score).
    if (in.ood_score > cfg_.ood_suspect) {
      stats.model[static_cast<int>(SlotId::E)].calls++;
      return {RouteAction::OOD, "ood_suspect"};
    }

    // Low margin / high entropy -> confusable-class expert (slot C stub), but once
    // the top-1 has been stable for stability_frames, reduce the expert cadence.
    if (in.stable_frames >= cfg_.stability_frames) {
      since_expert_++;
      if (since_expert_ < cfg_.expert_min_interval) {
        stats.model[static_cast<int>(SlotId::A)].calls++;
        stats.model[static_cast<int>(SlotId::A)].inference_us_total += primary_us;
        stats.busy_us_total += primary_us;
        return {RouteAction::DIRECT, "stable_suppressed_expert"};
      }
      since_expert_ = 0;
    }
    stats.model[static_cast<int>(SlotId::C)].calls++;
    stats.model[static_cast<int>(SlotId::C)].switches++;
    return {RouteAction::EXPERT, "low_margin_or_high_entropy"};
  }

 private:
  RouterConfig cfg_;
  int since_expert_ = 0;
};

}  // namespace m27

#endif  // M27_CONDITIONAL_ROUTER_HPP
