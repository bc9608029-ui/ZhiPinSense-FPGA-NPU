// touch.hpp — pure, host-testable touch decoding + coordinate mapping.
//
// The physical panel is 1024x600; the UI canvas is 1280x720.  The decoder maps
// an INPUT range onto the canvas with a full-range linear map:
//     canvas = (value - in_lo) * (canvas_size - 1) / (in_hi - in_lo)
// By default the input range is the panel (0..1023 x 0..599), i.e. the pure
// "1024x600 -> 1280x720" mapping the unit tests verify.  On the board, phase3
// sets the input range to the touch controller's calibrated axis min/max
// (read via EVIOCGABS), so raw ABS_X/ABS_MT_POSITION_X values map directly to
// canvas coordinates — equivalent to panel->canvas for a full-screen controller.
//
// It decodes both touch protocols:
//   * protocol A (single touch): ABS_X / ABS_Y + BTN_TOUCH
//   * protocol B (multi-touch): ABS_MT_SLOT / ABS_MT_TRACKING_ID /
//     ABS_MT_POSITION_X / ABS_MT_POSITION_Y
// A contact is "up" when its ABS_MT_TRACKING_ID is -1 (or BTN_TOUCH goes to 0).
//
// No device I/O here: the board program feeds this decoder one input_event at a
// time; unit tests feed synthetic events.  The device-open / re-enumeration /
// reconnect logic lives in phase3_touch_test.cpp, not here.

#pragma once

#include <cstdint>

namespace touch {

// Linux input event constants (evdev) — kept here so host tests don't need
// <linux/input.h>.
namespace ev {
    constexpr std::uint16_t EV_SYN             = 0x00;
    constexpr std::uint16_t EV_KEY             = 0x01;
    constexpr std::uint16_t EV_ABS             = 0x03;

    constexpr std::uint16_t SYN_REPORT         = 0x00;

    constexpr std::uint16_t ABS_X              = 0x00;
    constexpr std::uint16_t ABS_Y              = 0x01;
    constexpr std::uint16_t ABS_MT_SLOT        = 0x2f;
    constexpr std::uint16_t ABS_MT_POSITION_X  = 0x35;
    constexpr std::uint16_t ABS_MT_POSITION_Y  = 0x36;
    constexpr std::uint16_t ABS_MT_TRACKING_ID = 0x39;

    constexpr std::uint16_t BTN_TOUCH          = 0x14a;
}

class TouchDecoder {
public:
    explicit TouchDecoder(int canvas_w = 1280, int canvas_h = 720)
        : canvas_w_(canvas_w), canvas_h_(canvas_h) {
        // Default input range = the 1024x600 panel (pure panel->canvas mapping).
        set_input_range(0, 1023, 0, 599);
        reset();
    }

    // Set the calibrated input (touch-controller) axis min/max.  E.g. phase3
    // passes the values read from EVIOCGABS.
    void set_input_range(int x_lo, int x_hi, int y_lo, int y_hi);

    // Feed one input_event (type, code, value).  Returns true when a
    // SYN_REPORT has just completed a frame (read touching()/x()/y() then).
    bool feed(std::uint16_t type, std::uint16_t code, std::int32_t value);

    // True when a contact is currently down (tracking id >= 0, or BTN_TOUCH).
    bool touching() const { return active_; }

    // Current contact position mapped onto the CANVAS (0..canvas_w-1 / h-1).
    // Clamped; returns 0 when not touching.
    int x() const { return active_ ? map_x(cur_x_) : 0; }
    int y() const { return active_ ? map_y(cur_y_) : 0; }

    // Pure input->canvas mapping (full-range, clamped).
    int map_x(int v) const;
    int map_y(int v) const;

    void reset();

private:
    static constexpr int kMaxSlots = 16;

    int canvas_w_, canvas_h_;
    int x_lo_ = 0, x_hi_ = 1023, y_lo_ = 0, y_hi_ = 599;

    int cur_slot_ = 0;
    int slot_id_[kMaxSlots];
    int slot_x_[kMaxSlots];
    int slot_y_[kMaxSlots];
    int btn_touch_ = 0;         // protocol A fallback

    int cur_x_ = 0, cur_y_ = 0; // primary contact (raw input coords)
    bool active_ = false;
};

} // namespace touch
