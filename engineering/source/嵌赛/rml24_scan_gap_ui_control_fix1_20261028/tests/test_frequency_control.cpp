#include "../board_package/frequency_control.hpp"
#include <cassert>
#include <iostream>

static void tap_field(freqctl::FrequencyControlState& s,int i){
    int x0,y0,x1,y1;ui::mode_ui::frequency_rect(i,x0,y0,x1,y1);
    assert(s.on_release((x0+x1)/2,(y0+y1)/2).redraw);
}
static freqctl::FrequencyControlState::Action key(freqctl::FrequencyControlState& s,int i){
    int x0,y0,x1,y1;ui::mode_ui::keypad_rect(i,x0,y0,x1,y1);
    return s.on_release((x0+x1)/2,(y0+y1)/2);
}
int main(){
    freqctl::FrequencyControlState s;
    s.set_connected(true);
    s.on_reply("OK tuning=1 fixed_hz=2400000000 start_hz=2395000000 stop_hz=2405000000 step_hz=1000000 min_hz=2300000000 max_hz=2500000000 max_scan_points=101");
    assert(s.fixed_hz()==2400000000ULL);
    tap_field(s,0); key(s,7); // clear
    key(s,0);key(s,4);key(s,13);key(s,13); // 1400 -> out of range
    auto bad=key(s,15);assert(bad.command.empty()&&s.status()=="OUT OF RANGE");
    key(s,7);key(s,1);key(s,4);key(s,13);key(s,13); // 2400
    auto good=key(s,15);assert(good.command=="SET_FIXED_HZ 2400000000");
    s.on_reply("OK command_id=7 requested_fixed_hz=2400000000 applied_fixed_hz=2400000000");
    assert(!s.editor_open()&&s.status()=="APPLIED");
    tap_field(s,3);key(s,7);key(s,0); // 1 MHz
    auto scan=key(s,15);assert(scan.command=="SET_SCAN_RANGE_HZ 2395000000 2405000000 1000000");
    std::cout<<"frequency_control PASS\n";
}
