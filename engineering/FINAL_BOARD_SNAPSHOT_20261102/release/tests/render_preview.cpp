#include "../candidate/ui_sw/signal_history.hpp"
#include <fstream>
void write(const std::string& path,const std::vector<std::uint16_t>& data){
    std::ofstream f(path,std::ios::binary);f<<"P6\n1280 720\n255\n";
    for(auto v:data){unsigned char p[3]={static_cast<unsigned char>(((v>>11)&31)*255/31),
        static_cast<unsigned char>(((v>>5)&63)*255/63),static_cast<unsigned char>((v&31)*255/31)};f.write(reinterpret_cast<char*>(p),3);}
}
int main(){
    std::vector<std::uint16_t> px(1280*720);ui::Canvas c{px.data(),1280,720};
    ui::UiState s;s.status=ui::Status::Live;s.top1="QPSK";s.conf=.94;s.dist.assign(24,0);
    s.dist[4]=.94;s.dist[3]=.04;s.dist[5]=.02;s.classes=&ui::classes_24();s.work_mode="SWEEP";
    s.requested_mode="SWEEP";s.ctl_connected="CONTROL CONNECTED";s.class_count=24;
    s.meas.spectrum_center_hz=2400000000;s.frequency_status="SYNCED";
    ui::render_mode(c,ui::theme_default(),s);write("previews/tuning.ppm",px);
    ui::SignalHistory h;
    for(int i=0;i<10;++i){s.meas.spectrum_center_hz=2400000000+i*300000;h.observe(s,1793250000+i*60);}
    ui::history_ui::Window w;
    ui::render_main(c,ui::theme_default(),s);ui::history_ui::render(c,ui::theme_default(),h,w);write("previews/main.ppm",px);
    w.open=true;w.snapshot=h.rows;
    ui::render_main(c,ui::theme_default(),s);ui::history_ui::render(c,ui::theme_default(),h,w);write("previews/history.ppm",px);
    w.selected=0;w.detail=h.rows[0];ui::history_ui::render(c,ui::theme_default(),h,w);write("previews/detail.ppm",px);
}
