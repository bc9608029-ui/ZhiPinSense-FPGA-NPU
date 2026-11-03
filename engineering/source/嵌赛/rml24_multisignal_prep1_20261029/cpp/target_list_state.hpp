#pragma once

// target_list_state.hpp -- multi-target list page state model (C2).
//
// Consumes the parsed rml24_targets event and drives the five-page UI's list
// page: home summary, per-target selection, selected Top3 + update time,
// scroll/pagination on overflow, and the frozen "constellation/params show only
// the SELECTED target's valid data" rule (switching, expiring or unclassifying
// a target clears the old IQ/params).  Pure display logic; never touches RF and
// never reads ground-truth labels (class names arrive verbatim on the wire).
//
// FIXED mode: the producer never emits rml24_targets in FIXED mode, so this
// state is simply not applied there -- the original single-result behaviour is
// unchanged.  The renderer gates on the state event's work_mode == "BAND_SCAN".

#include "target_list_rml24_parse.hpp"

#include <algorithm>
#include <cstdint>
#include <string>
#include <vector>

namespace ui {

// Label shown for an unclassified target.  There is NO fabricated Top3 and the
// confidence is exactly 0.0 (enforced by the parser), so the list page renders
// this label instead of a class name.
inline const char* unclassified_label() {
    return "\xE6\x9C\xAA\xE5\x88\x86\xE7\xB1\xBB";  // "未分类" (UTF-8)
}

struct SelectFeedback {
    bool ok = false;
    std::string error;              // non-empty reason when !ok
    std::int64_t selected_target_id = -1;
};

class TargetListState {
public:
    static constexpr std::size_t kDefaultPageSize = 6;

    // Replace the list with a freshly parsed event.  Targets are kept sorted by
    // centre frequency (ascending) for a stable, scrollable list.  A vanished
    // selection falls back to none and clears the old IQ/params; a target that
    // became unclassified or expired likewise clears the params.
    void apply(const TargetListEvent& ev) {
        targets_ = ev.targets;
        std::sort(targets_.begin(), targets_.end(),
                  [](const TargetRecord& a, const TargetRecord& b) {
                      return a.center_hz < b.center_hz;
                  });
        update_time_us_ = ev.timestamp_us;
        if (selected_id_ >= 0) {
            const TargetRecord* sel = find_selected();
            if (sel == nullptr || !sel->classified() || sel->status == "expired") {
                selected_id_ = -1;
                params_valid_ = false;      // clear old IQ/params
            }
        }
        clamp_offset();
    }

    // ---- home page summary -------------------------------------------------
    std::size_t size() const { return targets_.size(); }
    bool empty() const { return targets_.empty(); }
    std::string summary_line() const {
        return "targets=" + std::to_string(targets_.size());
    }
    std::uint64_t update_time_us() const { return update_time_us_; }

    // ---- pagination (overflow scrolls, never clips silently) ---------------
    void set_page_size(std::size_t n) { page_size_ = (n == 0) ? 1 : n; clamp_offset(); }
    std::size_t page_count() const {
        if (targets_.empty()) return 0;
        return (targets_.size() + page_size_ - 1) / page_size_;
    }
    void set_page_offset(std::size_t off) { page_offset_ = off; clamp_offset(); }
    std::size_t page_offset() const { return page_offset_; }
    std::vector<const TargetRecord*> visible_page() const {
        std::vector<const TargetRecord*> out;
        const std::size_t begin = page_offset_ * page_size_;
        const std::size_t end = std::min(begin + page_size_, targets_.size());
        for (std::size_t i = begin; i < end; ++i) out.push_back(&targets_[i]);
        return out;
    }

    // ---- selection / feedback ---------------------------------------------
    SelectFeedback select(std::uint64_t target_id) {
        SelectFeedback f;
        for (const TargetRecord& t : targets_) {
            if (t.target_id == target_id) {
                selected_id_ = static_cast<std::int64_t>(target_id);
                // The constellation/params belong to the previous selection; a
                // switch replaces (clears) them, never accumulates.
                params_valid_ = t.classified() && t.status != "expired";
                f.ok = true;
                f.selected_target_id = selected_id_;
                return f;
            }
        }
        f.ok = false;
        f.error = "unknown target_id";
        f.selected_target_id = selected_id_;
        return f;
    }

    void clear_selection() {
        selected_id_ = -1;
        params_valid_ = false;
    }

    std::int64_t selected_target_id() const { return selected_id_; }

    const TargetRecord* selected() const {
        if (selected_id_ < 0) return nullptr;
        for (const TargetRecord& t : targets_) {
            if (static_cast<std::int64_t>(t.target_id) == selected_id_) return &t;
        }
        return nullptr;
    }

    // True only while the selected target has valid data to show (classified and
    // not expired).  The renderer draws the constellation/params page from this;
    // when false, the old IQ/params MUST be cleared (they belong to a previous
    // target or an unclassified/expired one).
    bool selected_has_valid_data() const { return params_valid_; }

    // Explicitly drop any cached IQ/params (e.g. on mode change to FIXED).
    void invalidate_iq() { params_valid_ = false; }

    // Top3 class name of the selected target, or the unclassified label.
    std::string selected_top1_label() const {
        const TargetRecord* t = selected();
        if (t == nullptr || !t->classified()) return unclassified_label();
        return t->top3.front().class_name;
    }

private:
    const TargetRecord* find_selected() const {
        if (selected_id_ < 0) return nullptr;
        for (const TargetRecord& t : targets_) {
            if (static_cast<std::int64_t>(t.target_id) == selected_id_) return &t;
        }
        return nullptr;
    }
    void clamp_offset() {
        const std::size_t pc = page_count();
        if (pc == 0) { page_offset_ = 0; return; }
        if (page_offset_ >= pc) page_offset_ = pc - 1;
    }

    std::vector<TargetRecord> targets_;
    std::int64_t selected_id_ = -1;
    std::size_t page_size_ = kDefaultPageSize;
    std::size_t page_offset_ = 0;
    std::uint64_t update_time_us_ = 0;
    bool params_valid_ = false;
};

}  // namespace ui
