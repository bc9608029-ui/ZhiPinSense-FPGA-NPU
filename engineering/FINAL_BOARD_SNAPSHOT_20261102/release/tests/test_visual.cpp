#include "../candidate/ui_sw/waterfall_render.cpp"
#include <cassert>
#include <vector>
#include <fstream>
#include <iostream>
int main(){
 assert(ui::curve_y(0)==116);assert(ui::curve_y(-480)==212);
 assert(ui::curve_y(0)<ui::curve_y(-240)&&ui::curve_y(-240)<ui::curve_y(-480));
 assert(ui::colormap_t(0)>ui::colormap_t(-240));
 std::vector<std::uint16_t> pixels(1280*720);ui::Canvas c{pixels.data(),1280,720};auto theme=ui::theme_default();
 ui::UiState s;s.status=ui::Status::Live;s.running=true;s.presence="SIGNAL_PRESENT";s.meas.valid=true;s.meas.spectrum_valid=true;s.meas.spectrum_sample_rate_hz=2560000;
 for(int i=0;i<256;++i){s.meas.spectrum_dbfs_x4[i]=-480;}s.meas.spectrum_dbfs_x4[64]=0;
 ui::WaterfallHistory h;ui::WaterfallHistory::Row row{};row.fill(-480);row[64]=0;assert(h.push(row.data(),1,1000));
 ui::render_spectrum_waterfall(c,theme,s,h);assert(pixels[120*1280+(96+64*3)]==theme.interactive);assert(pixels[120*1280+96]!=theme.interactive);
 assert(pixels[487*1280+(96+64*3)]!=pixels[487*1280+96]);
 std::ofstream out("visual_spectrum.ppm",std::ios::binary);out<<"P6\n1280 720\n255\n";
 for(auto v:pixels){unsigned char p[3]={static_cast<unsigned char>(((v>>11)&31)*255/31),static_cast<unsigned char>(((v>>5)&63)*255/63),static_cast<unsigned char>((v&31)*255/31)};out.write(reinterpret_cast<char*>(p),3);}
 std::cout<<"SPECTRUM_AXIS_AND_HEATMAP_PIXEL_TEST PASS\n";
}
