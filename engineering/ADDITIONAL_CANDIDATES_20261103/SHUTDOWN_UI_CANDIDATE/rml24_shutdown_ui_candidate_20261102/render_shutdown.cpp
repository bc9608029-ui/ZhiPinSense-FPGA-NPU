#include "ui_render.hpp"
#include "waterfall_render.hpp"
#include "waterfall_history.hpp"
#include <fstream>
#include <string>
#include <vector>
void write(const std::string& path,const std::vector<std::uint16_t>& px) {
    std::ofstream f(path,std::ios::binary);f<<"P6\n1280 720\n255\n";
    for(auto v:px){const unsigned char p[3]={static_cast<unsigned char>(((v>>11)&31)*255/31),
        static_cast<unsigned char>(((v>>5)&63)*255/63),static_cast<unsigned char>((v&31)*255/31)};
        f.write(reinterpret_cast<const char*>(p),3);}
}
int main(int argc,char** argv) {
    if(argc!=2) return 2;
    std::vector<std::uint16_t> px(1280*720);ui::Canvas c{px.data(),1280,720};
    ui::UiState s;s.status=ui::Status::Live;s.top1="QPSK";s.conf=.94;s.dist.assign(24,0);
    s.dist[4]=.94;s.dist[3]=.04;s.dist[5]=.02;s.classes=&ui::classes_24();s.work_mode="SWEEP";
    s.requested_mode="SWEEP";s.ctl_connected="CONTROL CONNECTED";s.class_count=24;
    s.meas.spectrum_center_hz=2400000000;s.frequency_status="SYNCED";
    ui::WaterfallHistory history;
    for(int page=0;page<5;++page){
        if(page==0)ui::render_main(c,ui::theme_default(),s);
        if(page==1)ui::render_parameters(c,ui::theme_default(),s,nullptr);
        if(page==2)ui::render_waterfall(c,ui::theme_default(),s,history);
        if(page==3)ui::render_constellation(c,ui::theme_default(),s);
        if(page==4)ui::render_mode(c,ui::theme_default(),s);
#ifdef SHUTDOWN_CANDIDATE
        ui::shutdown_ui::State state;
        ui::shutdown_ui::render(c,ui::theme_default(),state,page,false);
#endif
        write(std::string(argv[1])+"/page_"+std::to_string(page)+".ppm",px);
    }
#ifdef SHUTDOWN_CANDIDATE
    for(const auto phase:{ui::shutdown_ui::Phase::Confirm,ui::shutdown_ui::Phase::Pending,
                          ui::shutdown_ui::Phase::Queued,ui::shutdown_ui::Phase::Error}){
        ui::render_mode(c,ui::theme_default(),s);
        ui::shutdown_ui::State state;state.phase=phase;state.error="SHUTDOWN COMMAND FAILED";
        ui::shutdown_ui::render(c,ui::theme_default(),state,4,false);
        write(std::string(argv[1])+"/modal_"+std::to_string(static_cast<int>(phase))+".ppm",px);
    }
#endif
}
