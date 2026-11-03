// touch.cpp — touch decoding + input->canvas coordinate mapping (pure).

#include "touch.hpp"

namespace touch {

void TouchDecoder::set_input_range(int x_lo, int x_hi, int y_lo, int y_hi) {
    x_lo_ = x_lo;
    x_hi_ = x_hi;
    y_lo_ = y_lo;
    y_hi_ = y_hi;
}

int TouchDecoder::map_x(int v) const {
    if (x_hi_ == x_lo_) return 0;
    std::int64_t m = static_cast<std::int64_t>(v - x_lo_) * (canvas_w_ - 1) / (x_hi_ - x_lo_);
    if (m < 0) m = 0;
    if (m >= canvas_w_) m = canvas_w_ - 1;
    return static_cast<int>(m);
}

int TouchDecoder::map_y(int v) const {
    if (y_hi_ == y_lo_) return 0;
    std::int64_t m = static_cast<std::int64_t>(v - y_lo_) * (canvas_h_ - 1) / (y_hi_ - y_lo_);
    if (m < 0) m = 0;
    if (m >= canvas_h_) m = canvas_h_ - 1;
    return static_cast<int>(m);
}

void TouchDecoder::reset() {
    cur_slot_ = 0;
    for (int i = 0; i < kMaxSlots; ++i) {
        slot_id_[i] = -1;
        slot_x_[i] = 0;
        slot_y_[i] = 0;
    }
    btn_touch_ = 0;
    cur_x_ = 0;
    cur_y_ = 0;
    active_ = false;
}

bool TouchDecoder::feed(std::uint16_t type, std::uint16_t code, std::int32_t value) {
    if (type == ev::EV_ABS) {
        if (code == ev::ABS_MT_SLOT) {
            cur_slot_ = value < 0 ? 0 : (value >= kMaxSlots ? kMaxSlots - 1 : value);
        } else if (code == ev::ABS_MT_TRACKING_ID) {
            slot_id_[cur_slot_] = value;                 // -1 = contact up
        } else if (code == ev::ABS_MT_POSITION_X) {
            slot_x_[cur_slot_] = value;
        } else if (code == ev::ABS_MT_POSITION_Y) {
            slot_y_[cur_slot_] = value;
        } else if (code == ev::ABS_X) {                  // protocol A
            slot_x_[0] = value;
        } else if (code == ev::ABS_Y) {                  // protocol A
            slot_y_[0] = value;
        }
        return false;
    }

    if (type == ev::EV_KEY && code == ev::BTN_TOUCH) {
        btn_touch_ = value;
        return false;
    }

    if (type == ev::EV_SYN && code == ev::SYN_REPORT) {
        // Resolve the primary contact: the first slot with a live tracking id
        // (protocol B), else protocol A via BTN_TOUCH.
        active_ = false;
        for (int i = 0; i < kMaxSlots; ++i) {
            if (slot_id_[i] >= 0) {
                cur_x_ = slot_x_[i];
                cur_y_ = slot_y_[i];
                active_ = true;
                break;
            }
        }
        if (!active_ && btn_touch_ != 0) {
            cur_x_ = slot_x_[0];
            cur_y_ = slot_y_[0];
            active_ = true;
        }
        return true;
    }

    return false;
}

} // namespace touch
