#include "ui_render.hpp"
#include <vector>
#include <cassert>
#include <iostream>
int main(){std::vector<std::uint16_t>a(1280*720),b(a.size());ui::UiState s;s.status=ui::Status::NoSignal;s.work_mode="SWEEP";ui::Canvas ca{a.data(),1280,720},cb{b.data(),1280,720};ui::render_main(ca,ui::theme_default(),s);s.scan_progress="SCAN 3 / 11";ui::render_main(cb,ui::theme_default(),s);int n=0;for(int y=280;y<335;++y)for(int x=640;x<1000;++x)n+=a[y*1280+x]!=b[y*1280+x];assert(n>20);std::cout<<"NO_SIGNAL_SWEEP_PROGRESS_RENDER_PASS changed_pixels="<<n<<"\n";}
