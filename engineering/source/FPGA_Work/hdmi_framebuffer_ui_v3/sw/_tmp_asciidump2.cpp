#include "canvas.hpp"
#include "ui_renderer.hpp"
#include "model_contract.hpp"
#include <cstdio>
#include <vector>
#include <string>
static std::vector<float> peaked(int n, int top, float s){std::vector<float> l(n,1.0f);l[top]=s;return ui::softmax(l);}
static ui::UiState base(const std::vector<float>& p){
    ui::UiState s; model::Contract c=model::contract_v1_1();
    s.class_names=c.class_names;s.class_count=c.class_count;s.prob=p;
    s.source=ui::Source::Mock;s.is_mock=true;s.fpga_ok=true;s.npu_ok=false;
    s.frame_id=123456;s.fps=60.0f;s.render_latency_ms=1.23f;s.e2e_latency_ms=2.34f;
    s.fb_phys_addr=0x30100000ULL;s.frame_ctrl_version=0x20230218U;s.front_buffer=0;
    s.events={"BOOT OK","FB MAPPED 0x30100000","FRAME CTRL VER OK","MOCK SOURCE ACTIVE"};return s;}
static void dump(const char* name,const ui::UiState& st,ui::Page pg){
    ui::Renderer r; ui::Canvas c(1280,720); r.draw(c,st,pg);
    const int C=128,R=45,cw=1280/C,ch=720/R; const char* ramp=" .:-=+*#%@";
    std::printf("==== %s ====\n",name);
    for(int ry=0;ry<R;++ry){for(int rx=0;rx<C;++rx){
        long lit=0,tot=0;
        for(int y=ry*ch;y<(ry+1)*ch;++y)for(int x=rx*cw;x<(rx+1)*cw;++x){
            std::uint16_t p=c.get(x,y);int r=(p>>11)&0x1f,g=(p>>5)&0x3f,b=p&0x1f;
            int lum=(r*77+g*150+b*29)>>8; if(lum>110)++lit; ++tot;}
        int frac=tot?(int)(lit*9/tot):0; std::putchar(ramp[frac]);}
        std::putchar(10);}}
int main(){
    dump("OVERVIEW normal",base(peaked(10,7,5.0f)),ui::Page::Overview);
    dump("ALL CLASSES 10",base(peaked(10,7,4.5f)),ui::Page::AllClasses);
    dump("DIAGNOSTICS",base(peaked(10,7,4.5f)),ui::Page::Diagnostics);
    return 0;}
