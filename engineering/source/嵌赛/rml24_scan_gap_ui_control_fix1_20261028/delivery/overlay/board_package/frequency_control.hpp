#pragma once

// Touch numeric editor for the final FIXED/BAND_SCAN receiver.  Values are
// entered in MHz and emitted only through the existing fail-closed control
// protocol.  This class never writes SDR hardware directly.

#include "../ui_sw/ui_render.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <limits>
#include <sstream>
#include <string>

namespace freqctl {

enum class Field { None = -1, Fixed = 0, Start = 1, Stop = 2, Step = 3 };

class FrequencyControlState {
public:
    struct Action { bool redraw = false; std::string command; };

    void set_connected(bool value) {
        connected_ = value;
        if (!value && status_ == "PENDING") status_ = "DISCONNECTED";
    }

    void send_failed() {
        pending_ = false;
        status_ = "SEND FAILED";
    }

    bool editor_open() const { return field_ != Field::None; }
    int edit_field() const { return static_cast<int>(field_); }
    const std::string& edit_text() const { return text_; }
    const std::string& status() const { return status_; }
    std::uint64_t fixed_hz() const { return fixed_; }
    std::uint64_t start_hz() const { return start_; }
    std::uint64_t stop_hz() const { return stop_; }
    std::uint64_t step_hz() const { return step_; }

    // The receiver's GET_TUNING line is authoritative. Unknown fields are
    // ignored, malformed numeric values fail closed without changing state.
    void on_reply(const std::string& line) {
        if (line.rfind("OK tuning=1 ", 0) == 0) {
            std::uint64_t v = 0;
            if (value(line, "fixed_hz", v)) fixed_ = v;
            if (value(line, "start_hz", v)) start_ = v;
            if (value(line, "stop_hz", v)) stop_ = v;
            if (value(line, "step_hz", v)) step_ = v;
            if (value(line, "min_hz", v)) minimum_ = v;
            if (value(line, "max_hz", v)) maximum_ = v;
            if (value(line, "max_scan_points", v)) max_points_ = v;
            status_ = "SYNCED";
        } else if (line.rfind("OK accepted ", 0) == 0 && pending_) {
            status_ = "PENDING";
        } else if (line.rfind("OK command_id=", 0) == 0 && pending_) {
            // Final frequency-command ACK includes applied/read-back values.
            std::uint64_t v = 0; bool recognized = false;
            if (value(line, "applied_fixed_hz", v)) { fixed_ = v; recognized = true; }
            if (value(line, "requested_start_hz", v)) { start_ = v; recognized = true; }
            if (value(line, "requested_stop_hz", v)) { stop_ = v; recognized = true; }
            if (value(line, "requested_step_hz", v)) { step_ = v; recognized = true; }
            if (recognized) {
                pending_ = false; field_ = Field::None; text_.clear(); status_ = "APPLIED";
            }
        } else if (line.rfind("ERR", 0) == 0 && pending_) {
            pending_ = false; status_ = "REJECTED";
        }
    }

    Action on_release(int x, int y) {
        if (!editor_open()) {
            for (int i = 0; i < 4; ++i) {
                int x0,y0,x1,y1; ui::mode_ui::frequency_rect(i,x0,y0,x1,y1);
                if (inside(x,y,x0,y0,x1,y1)) {
                    field_ = static_cast<Field>(i);
                    text_ = mhz_text(current(field_));
                    status_ = "EDITING";
                    return {true,{}};
                }
            }
            return {};
        }
        for (int i = 0; i < 16; ++i) {
            int x0,y0,x1,y1; ui::mode_ui::keypad_rect(i,x0,y0,x1,y1);
            if (!inside(x,y,x0,y0,x1,y1)) continue;
            return key(i);
        }
        return {};
    }

    static const char* key_label(int i) {
        static const char* labels[16] = {
            "1","2","3","BACK", "4","5","6","CLEAR",
            "7","8","9","CANCEL", ".","0","000","APPLY"
        };
        return (i >= 0 && i < 16) ? labels[i] : "";
    }

private:
    static bool inside(int x,int y,int x0,int y0,int x1,int y1) {
        return x >= x0 && x <= x1 && y >= y0 && y <= y1;
    }
    static bool value(const std::string& line, const std::string& key, std::uint64_t& out) {
        const std::string needle = key + "=";
        const std::size_t p0 = line.find(needle);
        if (p0 == std::string::npos) return false;
        const std::size_t first = p0 + needle.size();
        const std::size_t last = line.find(' ', first);
        const std::string token = line.substr(first, last == std::string::npos ? last : last-first);
        if (token.empty() || token.find_first_not_of("0123456789") != std::string::npos) return false;
        char* end = nullptr; const unsigned long long v = std::strtoull(token.c_str(), &end, 10);
        if (!end || *end) return false;
        out = static_cast<std::uint64_t>(v); return true;
    }
    static std::string mhz_text(std::uint64_t hz) {
        std::ostringstream s; s << std::fixed << std::setprecision(6) << (hz / 1.0e6);
        std::string out=s.str(); while(out.size()>1 && out.back()=='0') out.pop_back();
        if(!out.empty() && out.back()=='.') out.pop_back(); return out;
    }
    std::uint64_t current(Field f) const {
        switch(f){case Field::Fixed:return fixed_;case Field::Start:return start_;
            case Field::Stop:return stop_;case Field::Step:return step_;default:return 0;}
    }
    bool parse_hz(std::uint64_t& out) const {
        if (text_.empty() || text_.size() > 16) return false;
        if (std::count(text_.begin(),text_.end(),'.') > 1 ||
            text_.find_first_not_of("0123456789.") != std::string::npos) return false;
        char* end=nullptr; const double mhz=std::strtod(text_.c_str(),&end);
        if(!end || *end || !std::isfinite(mhz) || mhz<=0.0) return false;
        const double hz=mhz*1.0e6;
        if(hz > static_cast<double>(std::numeric_limits<long long>::max())) return false;
        out=static_cast<std::uint64_t>(std::llround(hz)); return true;
    }
    bool valid_range(std::uint64_t a,std::uint64_t b,std::uint64_t c) const {
        if(a<minimum_ || b>maximum_ || a>=b || c==0 || c>2304000ULL) return false;
        const std::uint64_t points=(b-a+c-1)/c+1;
        return points<=max_points_;
    }
    Action key(int i) {
        const std::string k=key_label(i);
        if(k=="BACK") { if(!text_.empty()) text_.pop_back(); return {true,{}}; }
        if(k=="CLEAR") { text_.clear(); return {true,{}}; }
        if(k=="CANCEL") { field_=Field::None;text_.clear();status_="CANCELLED";return {true,{}}; }
        if(k=="APPLY") {
            if(!connected_) {status_="DISCONNECTED";return {true,{}};}
            std::uint64_t hz=0; if(!parse_hz(hz)){status_="INVALID NUMBER";return {true,{}};}
            std::uint64_t a=start_,b=stop_,c=step_;
            if(field_==Field::Fixed){
                if(hz<minimum_||hz>maximum_){status_="OUT OF RANGE";return {true,{}};}
                pending_=true;status_="PENDING";
                return {true,"SET_FIXED_HZ "+std::to_string(hz)};
            }
            if(field_==Field::Start)a=hz; else if(field_==Field::Stop)b=hz; else c=hz;
            if(!valid_range(a,b,c)){status_="INVALID RANGE";return {true,{}};}
            // Optimistically show the requested triplet while the producer remains
            // authoritative; a rejection leaves the previous applied values after
            // the next GET_TUNING sync.
            start_=a;stop_=b;step_=c;pending_=true;status_="PENDING";
            return {true,"SET_SCAN_RANGE_HZ "+std::to_string(a)+" "+std::to_string(b)+" "+std::to_string(c)};
        }
        if(text_.size()<16) text_+=k;
        return {true,{}};
    }

    Field field_=Field::None;
    std::string text_,status_="--";
    bool connected_=false,pending_=false;
    std::uint64_t fixed_=2400000000ULL,start_=2395000000ULL,stop_=2405000000ULL,step_=1000000ULL;
    std::uint64_t minimum_=2300000000ULL,maximum_=2500000000ULL,max_points_=101;
};

} // namespace freqctl

