#pragma once
// Summary only: never stores live IQ, waterfall pixels or device-control state.
#include "ui_render.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <numeric>
#include <sstream>

namespace ui {
struct SignalRecord {
    std::uint64_t first=0, last=0, hz=0, count=0;
    int mode=0;
    std::array<int,3> indices{{0,1,2}};
    std::array<float,3> probabilities{{0,0,0}};
};
inline const char* history_mode(int mode) {
    return mode==2 ? "SWEEP" : (mode==1 ? "SEARCH LOCK" : "FIXED");
}
inline std::string history_time(std::uint64_t value) {
    const std::time_t t=static_cast<std::time_t>(value);
    const std::tm* tm=std::localtime(&t);
    char b[32]={};
    if(tm) std::strftime(b,sizeof(b),"%m-%d %H:%M:%S",tm);
    return b;
}
class SignalHistory {
public:
    std::vector<SignalRecord> rows;
    std::uint64_t revision=0;
    std::string error;

    bool observe(const UiState& st,std::uint64_t now) {
        const double hz=st.meas.spectrum_center_hz;
        if(st.status!=Status::Live || !std::isfinite(hz) || hz<=0 || hz>6000000000.0 ||
           st.dist.size()!=24 || !now) return false;
        float total=0;
        for(float p:st.dist) {if(!std::isfinite(p)||p<0||p>1)return false;total+=p;}
        if(std::abs(total-1.0f)>0.01f)return false;
        SignalRecord r;
        r.hz=static_cast<std::uint64_t>(std::llround(hz));r.first=r.last=now;r.count=1;
        r.mode=st.work_mode=="SWEEP" ? 2 : (st.work_mode=="SEARCH LOCK" ? 1 : 0);
        std::array<int,24> ids{};std::iota(ids.begin(),ids.end(),0);
        std::stable_sort(ids.begin(),ids.end(),[&](int a,int b){return st.dist[a]>st.dist[b];});
        for(int j=0;j<3;++j){r.indices[j]=ids[j];r.probabilities[j]=st.dist[ids[j]];}
        // The latest summary at a frequency is updated; no frame-by-frame row spam.
        // Frequency tolerance is an explicit UI grouping policy, not RF resolution.
        for(auto it=rows.begin();it!=rows.end();++it){
            const auto delta=r.hz>it->hz ? r.hz-it->hz : it->hz-r.hz;
            if(delta<=10000 && now>=it->last){
                r.first=it->first;r.count=it->count+1;
                rows.erase(it);rows.insert(rows.begin(),r);++revision;return true;
            }
        }
        rows.insert(rows.begin(),r);if(rows.size()>10)rows.resize(10);
        ++revision;return true;
    }
    void clear(){rows.clear();++revision;}
    bool save(const std::string& path){
        if(path.empty())return true;
        const std::string temp=path+".tmp";
        std::ofstream f(temp,std::ios::trunc);
        if(!f){error="HISTORY SAVE FAILED";return false;}
        f<<"RML24_HISTORY_V1\n"<<std::setprecision(9);
        for(const auto& r:rows){
            f<<r.first<<' '<<r.last<<' '<<r.hz<<' '<<r.count<<' '<<r.mode;
            for(int j=0;j<3;++j)f<<' '<<r.indices[j]<<' '<<r.probabilities[j];
            f<<'\n';
        }
        f.flush();const bool ok=bool(f);f.close();
        if(!ok || std::rename(temp.c_str(),path.c_str())!=0){error="HISTORY SAVE FAILED";return false;}
        error.clear();return true;
    }
    bool load(const std::string& path){
        if(path.empty())return true;
        std::ifstream f(path);if(!f)return true;
        std::string line;if(!std::getline(f,line)||line!="RML24_HISTORY_V1"){error="HISTORY FILE INVALID";return false;}
        std::vector<SignalRecord> parsed;
        while(std::getline(f,line)){
            if(parsed.size()>=10){error="HISTORY FILE INVALID";return false;}
            std::istringstream s(line);SignalRecord r;
            if(!(s>>r.first>>r.last>>r.hz>>r.count>>r.mode)){error="HISTORY FILE INVALID";return false;}
            for(int j=0;j<3;++j){
                if(!(s>>r.indices[j]>>r.probabilities[j])||r.indices[j]<0||r.indices[j]>=24||
                   !std::isfinite(r.probabilities[j])||r.probabilities[j]<0||r.probabilities[j]>1){
                    error="HISTORY FILE INVALID";return false;
                }
            }
            std::string extra;
            if(s>>extra || !r.first || r.last<r.first || !r.count || !r.hz || r.hz>6000000000ULL ||
               r.mode<0||r.mode>2){error="HISTORY FILE INVALID";return false;}
            parsed.push_back(r);
        }
        rows=std::move(parsed);++revision;error.clear();return true;
    }
};

namespace history_ui {
inline void fill_rect(Canvas& c,int x0,int y0,int x1,int y1,std::uint16_t color){
    x0=std::max(x0,0);y0=std::max(y0,0);x1=std::min(x1,c.w-1);y1=std::min(y1,c.h-1);
    for(int y=y0;y<=y1;++y)for(int x=x0;x<=x1;++x)c.px[y*c.w+x]=color;
}
inline void outline_rect(Canvas& c,int x0,int y0,int x1,int y1,std::uint16_t color,int width){
    fill_rect(c,x0,y0,x1,y0+width-1,color);fill_rect(c,x0,y1-width+1,x1,y1,color);
    fill_rect(c,x0,y0,x0+width-1,y1,color);fill_rect(c,x1-width+1,y0,x1,y1,color);
}
struct Rect{int x0,y0,x1,y1;bool hit(int x,int y)const{return x>=x0&&x<=x1&&y>=y0&&y<=y1;}};
constexpr Rect open_button{1030,280,1254,332};
constexpr Rect back_button{1060,82,1234,138};
constexpr Rect previous{46,556,228,612},next{242,556,424,612},clear{1000,556,1234,612};
constexpr Rect cancel_clear{650,385,900,455},confirm_clear{930,385,1180,455};
inline Rect row_rect(int i){return {46,164+i*74,1234,230+i*74};}
class Window {
public:
    bool open=false,confirm=false;
    int page=0,selected=-1;
    std::uint64_t revision=0;
    std::vector<SignalRecord> snapshot;
    // Consume the entire press+release sequence; a drag out never triggers.
    bool sample(bool down,int x,int y,bool valid,bool main,SignalHistory& store){
        bool changed=false;
        if(down&&!was_down){sx=x;sy=y;armed=valid&&(open||main);drag=false;}
        if(down&&(std::abs(x-sx)>24||std::abs(y-sy)>24))drag=true;
        if(!down&&was_down&&armed&&!drag&&valid){
            if(!open&&main&&open_button.hit(sx,sy)&&open_button.hit(x,y)){open=true;page=0;selected=-1;snapshot=store.rows;changed=true;}
            else if(open){
                if(back_button.hit(sx,sy)&&back_button.hit(x,y)){
                    if(selected>=0)selected=-1;else{open=false;confirm=false;}changed=true;
                }else if(confirm){
                    if(confirm_clear.hit(sx,sy)&&confirm_clear.hit(x,y)){store.clear();snapshot.clear();confirm=false;selected=-1;page=0;changed=true;}
                    else if(cancel_clear.hit(sx,sy)&&cancel_clear.hit(x,y)){confirm=false;changed=true;}
                }else if(selected<0){
                    if(previous.hit(sx,sy)&&previous.hit(x,y)){page=0;changed=true;}
                    else if(next.hit(sx,sy)&&next.hit(x,y)){page=1;changed=true;}
                    else if(clear.hit(sx,sy)&&clear.hit(x,y)){confirm=true;changed=true;}
                    else for(int i=0;i<5;++i)if(row_rect(i).hit(sx,sy)&&row_rect(i).hit(x,y)&&page*5+i<int(snapshot.size())){
                        selected=page*5+i;detail=snapshot[selected];changed=true;
                    }
                }
            }
        }
        was_down=down;if(changed)++revision;return changed;
    }
    SignalRecord detail; // pinned copy; new live results cannot change an open detail
private:
    bool was_down=false,armed=false,drag=false;int sx=0,sy=0;
};

inline void button(Canvas& c,const Theme& th,const Rect& r,const std::string& text,bool emphasis=false){
    fill_rect(c,r.x0,r.y0,r.x1,r.y1,emphasis?th.selected:th.surface_alt);
    outline_rect(c,r.x0,r.y0,r.x1,r.y1,th.interactive,1);
    draw_text_center(c,text,(r.x0+r.x1)/2,(r.y0+r.y1)/2+8,th.text_primary,font_get(Weight::Bold,20));
}
inline std::string mhz(std::uint64_t hz){std::ostringstream s;s<<std::fixed<<std::setprecision(6)<<hz/1e6<<" MHz";return s.str();}
inline void render(Canvas& c,const Theme& th,const SignalHistory& h,const Window& w){
    const auto* b=font_get(Weight::Bold,28);const auto* r=font_get(Weight::Regular,20);
    if(!w.open){button(c,th,open_button,"HISTORY  "+std::to_string(h.rows.size())+"/10");return;}
    fill_rect(c,24,76,1255,624,th.background);
    draw_text(c,w.selected>=0?"SIGNAL HISTORY / DETAIL":"SIGNAL HISTORY",46,118,th.text_primary,b);
    button(c,th,back_button,w.selected>=0?"BACK":"CLOSE");
    if(w.selected>=0){
        const auto& d=w.detail;
        draw_text(c,"HISTORICAL SNAPSHOT - not live IQ or current measurements",46,170,th.warning,r);
        draw_text(c,mhz(d.hz),46,230,th.text_primary,font_get(Weight::Bold,40));
        draw_text(c,std::string(history_mode(d.mode))+"   last seen "+history_time(d.last),46,273,th.text_secondary,r);
        draw_text(c,"First seen "+history_time(d.first)+"   detections "+std::to_string(d.count),46,309,th.text_secondary,r);
        for(int i=0;i<3;++i){
            const int y=360+i*68;const auto& label=classes_24()[d.indices[i]];
            fill_rect(c,46,y-29,1234,y+24,th.surface);
            draw_text(c,std::to_string(i+1)+"   "+label,66,y+6,th.text_primary,b);
            char p[24];std::snprintf(p,sizeof(p),"%.1f%%",d.probabilities[i]*100);
            draw_text_right(c,p,1208,y+6,i==0?th.success:th.text_secondary,b);
        }
    }else{
        for(int i=0;i<5;++i){
            const int idx=w.page*5+i;const Rect rr=row_rect(i);
            fill_rect(c,rr.x0,rr.y0,rr.x1,rr.y1,th.surface);
            if(idx>=int(w.snapshot.size())){draw_text(c,"--",70,rr.y0+40,th.text_secondary,r);continue;}
            const auto& d=w.snapshot[idx];
            fill_rect(c,rr.x0,rr.y0,rr.x0+3,rr.y1,th.selected);
            draw_text(c,mhz(d.hz),66,rr.y0+28,th.text_primary,font_get(Weight::Bold,24));
            draw_text(c,std::string(history_mode(d.mode))+"  "+history_time(d.last),66,rr.y0+54,th.text_secondary,r);
            draw_text(c,classes_24()[d.indices[0]],625,rr.y0+34,th.text_primary,b);
            char p[32];std::snprintf(p,sizeof(p),"%.1f%%  >",d.probabilities[0]*100);
            draw_text_right(c,p,1214,rr.y0+34,th.success,b);
        }
        button(c,th,previous,"PREVIOUS");button(c,th,next,"NEXT");button(c,th,clear,"CLEAR HISTORY");
        draw_text(c,"PAGE "+std::to_string(w.page+1)+" / 2    RECENT "+std::to_string(w.snapshot.size())+" / 10",465,591,th.text_secondary,r);
        draw_text(c,"Snapshot - close and reopen to refresh",46,151,th.text_secondary,r);
        if(w.confirm){
            fill_rect(c,600,260,1234,485,th.surface_alt);outline_rect(c,600,260,1234,485,th.warning,2);
            draw_text(c,"Clear all 10 history slots?",630,320,th.text_primary,b);
            draw_text(c,"Live reception will continue.",630,357,th.text_secondary,r);
            button(c,th,cancel_clear,"CANCEL");button(c,th,confirm_clear,"CLEAR",true);
        }
    }
    if(!h.error.empty())draw_text(c,h.error,46,616,th.error,r);
}
} // history_ui
} // ui
