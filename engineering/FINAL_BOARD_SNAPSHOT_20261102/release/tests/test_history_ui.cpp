#include "../candidate/ui_sw/signal_history.hpp"
#include "../candidate/board_package/touch_mode_control.hpp"
#include "../candidate/board_package/frequency_control.hpp"
#include "../candidate/board_package/result_frame_v2_parse.hpp"
#include <cassert>
#include <iostream>

int main(){
    assert(ui::history_time(0)=="00:00:00");
    assert(ui::history_time(3661)=="01:01:01");
    assert(ui::history_time(360000)=="100:00:00");
    ui::SignalHistory h;ui::UiState s;s.status=ui::Status::Live;
    s.dist.assign(24,0);s.dist[3]=.8f;s.dist[4]=.15f;s.dist[0]=.05f;
    s.meas.spectrum_center_hz=2400000000.0;s.work_mode="FIXED";
    assert(h.observe(s,100));assert(h.observe(s,101));assert(h.rows.size()==1&&h.rows[0].count==2);
    {ui::SignalHistory h2;assert(h2.observe(s,0));
        ui::UiState changed=s;changed.dist[3]=.15f;changed.dist[4]=.8f;
        assert(!h2.observe(changed,1));assert(!h2.observe(changed,2));
        assert(h2.observe(changed,3));assert(h2.rows.size()==2);
        assert(h2.rows[0].indices[0]==4&&h2.rows[1].indices[0]==3);
        assert(h2.observe(changed,4));assert(h2.rows.size()==2);
        h2.rows[0].boot="previous-boot";assert(h2.save("history_test.tmp"));
        ui::SignalHistory h3;assert(h3.load("history_test.tmp"));
        assert(h3.rows[0].boot!=h3.boot_id);std::remove("history_test.tmp");}
    {ui::SignalHistory sweep;auto v=s;v.work_mode="SWEEP";
        assert(sweep.observe(v,100));
        v.dist.assign(24,0);v.dist[4]=1;assert(sweep.observe(v,130));
        assert(sweep.rows.size()==2&&sweep.rows[0].indices[0]==4&&sweep.rows[0].count==1);
        v.dist.assign(24,0);v.dist[5]=1;assert(sweep.observe(v,160));
        assert(sweep.rows.size()==3&&sweep.rows[0].indices[0]==5&&sweep.rows[1].indices[0]==4&&sweep.rows[2].indices[0]==3);
        assert(sweep.observe(v,190));assert(sweep.rows.size()==3&&sweep.rows[0].count==2);
    }
    {ui::SignalHistory search;auto v=s;v.work_mode="SEARCH LOCK";
        assert(search.observe(v,100));v.dist.assign(24,0);v.dist[4]=1;
        assert(!search.observe(v,101));assert(!search.observe(v,102));assert(search.observe(v,103));
        assert(search.rows.size()==2&&search.rows[0].count==3);
    }
    s.work_mode="SWEEP";assert(h.observe(s,102));assert(h.rows.size()==1&&h.rows[0].mode==2);
    for(int i=0;i<12;++i){s.meas.spectrum_center_hz+=100000;assert(h.observe(s,103+i));}
    assert(h.rows.size()==10);assert(h.rows.front().count==1);
    const auto rev=h.revision;s.status=ui::Status::NoSignal;assert(!h.observe(s,200));assert(h.revision==rev);
    assert(h.save("history_test.tmp"));ui::SignalHistory loaded;assert(loaded.load("history_test.tmp"));
    assert(loaded.rows.size()==10&&loaded.rows[0].hz==h.rows[0].hz);std::remove("history_test.tmp");
    {std::ofstream broken("history_test.tmp");broken<<"bad header\n";}
    assert(!loaded.load("history_test.tmp"));assert(loaded.rows.size()==10);std::remove("history_test.tmp");
    s.status=ui::Status::Live;s.dist[3]=std::numeric_limits<float>::quiet_NaN();
    assert(!h.observe(s,220));s.dist[3]=.8f;
    ui::history_ui::Window w;
    auto tap=[&](int x,int y){w.sample(true,x,y,true,true,h);w.sample(false,x,y,true,true,h);};
    tap(1100,310);assert(w.open);tap(300,580);assert(w.page==1);
    tap(100,190);assert(w.selected==5);const auto pin=w.detail.hz;
    s.status=ui::Status::Live;s.meas.spectrum_center_hz+=100000;h.observe(s,220);
    assert(w.detail.hz==pin);tap(1100,110);assert(w.selected==-1);tap(1100,580);assert(w.confirm);
    tap(1000,420);assert(h.rows.empty()&&!w.confirm);tap(1100,110);assert(!w.open);
    mctl::ModeControlState ctl;std::string cmd;
    assert(ctl.request(ui::mode_ui::kBtnSweep,0,cmd));assert(cmd=="SET_MODE CONTINUOUS_SCAN");
    mode_ctl::ModeKind mode;assert(mode_ctl::mode_from_token("CONTINUOUS SCAN",mode));
    assert(std::string(mode_ctl::mode_display_name(mode))=="SWEEP");
    ctl.on_sent(cmd,1);ctl.on_reply("OK accepted command_id=19 SET_MODE CONTINUOUS_SCAN",2);
    ctl.on_reply("OK applied command_id=19 SET_MODE CONTINUOUS_SCAN",3);
    assert(ctl.applied_mode_display()=="SWEEP");
    freqctl::FrequencyControlState freq;
    freq.on_reply("OK tuning=1 scan_index=3 scan_points=11 fixed_hz=2400000000");
    assert(freq.scan_progress()=="SCAN 3 / 11");
    mctl::ControlTapDetector detector(0);
    ui_touch::Point point;point.x=1100;point.y=310;point.valid=true;
    detector.on_sample(true,point,0);point.valid=false;detector.on_sample(false,point,1);
    point.x=1000;point.y=100;point.valid=true;
    detector.on_sample(true,point,2);assert(detector.on_sample(false,point,3)==ui::mode_ui::kBtnSweep);
    for(int i=0;i<ui::mode_ui::kBtnCount;++i){int x0,y0,x1,y1;ui::mode_ui::button_rect(i,x0,y0,x1,y1);
        assert(x0>=0&&x1<1280&&y0>=0&&y1<630&&y1-y0>=48);}
    std::cout<<"HISTORY_AND_MODE_TEST PASS\n";
}
