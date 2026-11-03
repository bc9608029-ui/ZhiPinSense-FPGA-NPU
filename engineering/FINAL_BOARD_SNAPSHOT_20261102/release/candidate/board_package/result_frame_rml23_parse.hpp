#pragma once

// result_frame_rml23_parse.hpp — strict JSON-lines validator for the RML23
// 23-class chain result record (M29 Phase F5, schema "rml23-chain-v2").
//
// The parsing machinery lives in result_frame_v2_parse.hpp (ui::detail::JsonReader),
// which this header extends with the 23-class contract.  The schema is DISTINCT
// from the 12-class chain so the old 12-class parser can never misread a 23-dim
// record:
//
//   type == "result", version == "rml23-chain-v2",
//   model_mode == "RML23-AMSSB-MERGED", class_count == 23,
//   argmax_idx in [0,22], argmax_class == cat::label(target_23(), argmax_idx),
//   merged_23_top1 == argmax_idx, raw_24_top1 in [0,23],
//   deployment_mode == "AMSSB_MERGED",
//   expert_enabled == false, expert_result == "NOT_RUN",
//   probabilities length 23, finite in [0,1], |sum-1| <= 1e-3,
//   confidence == probabilities[argmax_idx] (tol 1e-4),
//   model_sha non-empty; all numeric fields finite (snr_db may be null).
//   Runtime fields (presence_state, level_mode, model_scale, rf_gain_db,
//   work_mode, run_state, measurements) are REQUIRED (they are always emitted by
//   result_frame_rml23_line()).
//
// iCraft-free, libiio-free, header-only; host-testable on WSL.

#include "result_frame_v2_parse.hpp"   // ui::detail::JsonReader + ParseOutcome

namespace ui {

// Strict 23-class result-frame validator (M29 Phase F5).  Never throws; returns
// ok=false + error on any malformed input or contract violation.  Rejects any
// record whose `version` is not "rml23-chain-v2" (12class-chain-v1/v2 records are
// owned by parse_result_frame_v2 and are NOT accepted here).
inline ParseOutcome parse_result_frame_rml23(const std::string& line) {
    ParseOutcome o;
    detail::JsonReader r(line);
    if (!r.parse_record_rml23(o.frame, o.error)) {
        o.ok = false;
        return o;
    }
    o.ok = true;
    return o;
}

}  // namespace ui
