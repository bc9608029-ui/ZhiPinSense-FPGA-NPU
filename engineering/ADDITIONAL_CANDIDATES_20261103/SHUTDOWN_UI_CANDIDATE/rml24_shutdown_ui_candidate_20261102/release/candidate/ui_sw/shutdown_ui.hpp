#pragma once
#include <cstdint>
#include <string>

namespace ui {
struct Canvas;
struct Theme;
namespace shutdown_ui {
struct Rect {
    int x0, y0, x1, y1;
    bool contains(int x, int y) const { return x >= x0 && x <= x1 && y >= y0 && y <= y1; }
};
constexpr Rect kButton{1000, 480, 1235, 543};
constexpr Rect kCancel{315, 395, 605, 470};
constexpr Rect kConfirm{675, 395, 965, 470};
enum class Phase { Idle, Confirm, Pending, Queued, Error };
struct State {
    Phase phase = Phase::Idle;
    bool down = false;
    int pressed = 0;
    std::uint64_t revision = 0;
    std::string error;
    bool modal() const { return phase != Phase::Idle; }
    void cancel_touch() { down=false; pressed=0; ++revision; }
    void fail(const std::string& text) { error = text; phase = Phase::Error; ++revision; }
    // Consumes the full down/up sequence. A single held touch cannot confirm.
    bool sample(bool touching, int x, int y, bool valid, bool button_enabled, bool& request) {
        request = false;
        const bool owned = modal() || pressed != 0;
        if (touching && !down) {
            down = true; pressed = 0;
            if (valid) {
                if (phase == Phase::Idle && button_enabled && kButton.contains(x,y)) pressed = 1;
                else if ((phase == Phase::Confirm || phase == Phase::Error) && kCancel.contains(x,y)) pressed = 2;
                else if (phase == Phase::Confirm && kConfirm.contains(x,y)) pressed = 3;
            }
            if (pressed) ++revision;
        } else if (touching && down && pressed) {
            const Rect& rect = pressed == 1 ? kButton : pressed == 2 ? kCancel : kConfirm;
            if (!valid || !rect.contains(x,y)) { pressed = 0; ++revision; }
        } else if (!touching && down) {
            down = false;
            const int target = pressed; pressed = 0;
            if (target) ++revision;
            if (valid) {
                if (target == 1 && button_enabled && phase == Phase::Idle && kButton.contains(x,y)) {
                    phase = Phase::Confirm; ++revision;
                } else if (target == 2 && kCancel.contains(x,y)) {
                    phase = Phase::Idle; error.clear(); ++revision;
                } else if (target == 3 && phase == Phase::Confirm && kConfirm.contains(x,y)) {
                    phase = Phase::Pending; request = true; ++revision;
                }
            }
            return owned || target != 0 || modal();
        }
        return owned || pressed != 0 || modal();
    }
};
void render(Canvas& canvas, const Theme& theme, const State& state, int page, bool editor_open);
} // namespace shutdown_ui
} // namespace ui
