#include "release/candidate/ui_sw/ui_render.hpp"
#include <cassert>
#include <iostream>
using namespace ui::shutdown_ui;
bool sample(State& s, bool down, int x, int y, bool enabled=true, bool valid=true) {
    bool request=false; s.sample(down,x,y,valid,enabled,request); return request;
}
void tap(State& s,int x,int y,bool enabled=true) {
    assert(!sample(s,true,x,y,enabled)); assert(!sample(s,false,x,y,enabled));
}
int main() {
    int checks=0;
    State s;
    tap(s,1100,510,false); assert(s.phase==Phase::Idle); ++checks;
    tap(s,100,110); assert(s.phase==Phase::Idle); ++checks;
    assert(!sample(s,true,1100,510));
    assert(!sample(s,true,1100,510)); assert(s.phase==Phase::Idle); ++checks;
    assert(!sample(s,false,1100,510)); assert(s.phase==Phase::Confirm); ++checks;
    tap(s,1100,510); assert(s.phase==Phase::Confirm); ++checks;
    tap(s,400,430); assert(s.phase==Phase::Idle); ++checks;
    sample(s,true,1100,510); sample(s,true,900,510); sample(s,true,1100,510);
    assert(!sample(s,false,1100,510)); assert(s.phase==Phase::Idle); ++checks;
    sample(s,true,1100,510); sample(s,false,1100,510,true,false);
    assert(s.phase==Phase::Idle); ++checks;
    tap(s,1100,510); assert(s.phase==Phase::Confirm);
    sample(s,true,800,430); sample(s,true,800,430);
    assert(s.phase==Phase::Confirm); ++checks;
    assert(sample(s,false,800,430)); assert(s.phase==Phase::Pending); ++checks;
    assert(!sample(s,true,800,430)); assert(!sample(s,false,800,430));
    assert(s.phase==Phase::Pending); ++checks;
    s.phase=Phase::Queued; tap(s,400,430); assert(s.phase==Phase::Queued); ++checks;
    s.fail("TEST MODE - NO POWER OFF"); assert(s.phase==Phase::Error);
    tap(s,400,430); assert(s.phase==Phase::Idle); ++checks;
    assert(kButton.y0>ui::mode_ui::kRunY1 && kButton.y1<558); ++checks;
    assert(kButton.y1-kButton.y0>=60 && kCancel.y1-kCancel.y0>=60); ++checks;
    tap(s,1100,510); sample(s,true,800,430); s.cancel_touch();
    assert(!sample(s,false,800,430)); assert(s.phase==Phase::Confirm); ++checks;
    std::cout<<"SHUTDOWN_TOUCH_STATE_PASS checks="<<checks<<"\n";
}
