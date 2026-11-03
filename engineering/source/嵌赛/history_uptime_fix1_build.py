from pathlib import Path
import shutil
root=Path('F:/嵌赛/rml24_history_uptime_fix1_20261029')
src=Path('F:/嵌赛/rml24_sweep_history_20261029')
root.mkdir(exist_ok=False)
shutil.copytree(src/'candidate',root/'candidate',ignore=shutil.ignore_patterns('bin','__pycache__','*.pyc'))
for d in ['tests','scripts','evidence','previews','dist']:(root/d).mkdir()
for n in ['render_preview.cpp','test_history_ui.cpp']:shutil.copyfile(src/'tests'/n,root/'tests'/n)
shutil.copyfile(src/'scripts/check_cpp.sh',root/'scripts/check_cpp.sh')
p=root/'candidate/ui_sw/signal_history.hpp';s=p.read_text(encoding='utf-8')
s=s.replace('#include <ctime>','#include <ctime>\n#include <time.h>')
s=s.replace('    int mode=0;','    int mode=0;\n    std::string boot;')
a=s.index('inline std::string history_time(');b=s.index('class SignalHistory',a)
s=s[:a]+'''inline std::uint64_t history_uptime_seconds(){
    timespec t{};
    if(clock_gettime(CLOCK_BOOTTIME,&t)!=0) throw std::runtime_error("boot clock unavailable");
    return static_cast<std::uint64_t>(t.tv_sec);
}
inline std::string history_time(std::uint64_t value){
    std::ostringstream s;s<<std::setfill('0')<<std::setw(2)<<value/3600<<":"
        <<std::setw(2)<<(value/60)%60<<":"<<std::setw(2)<<value%60;return s.str();
}
inline std::string history_boot_id(){
    std::ifstream f("/proc/sys/kernel/random/boot_id");std::string id;
    if(!(f>>id))throw std::runtime_error("boot identity unavailable");return id;
}
''' +s[b:]
s=s.replace('    std::string error;','    std::string error;\n    const std::string boot_id=history_boot_id();\n    struct Pending {std::uint64_t hz,first;int label,hits;};\n    std::vector<Pending> pending;')
s=s.replace('st.dist.size()!=24 || !now','st.dist.size()!=24')
s=s.replace('SignalRecord r;\n        r.hz','SignalRecord r;r.boot=boot_id;\n        r.hz')
a=s.index('        // The latest summary');b=s.index('        rows.insert(rows.begin(),r);if',a)
s=s[:a]+'''        // Only the latest observation episode at this frequency can be updated.
        auto current=rows.end();
        for(auto it=rows.begin();it!=rows.end();++it){
            auto delta=r.hz>it->hz?r.hz-it->hz:it->hz-r.hz;
            if(delta<=10000 && it->boot==boot_id){current=it;break;}
        }
        auto pi=std::find_if(pending.begin(),pending.end(),[&](const Pending& p){
            return (r.hz>p.hz?r.hz-p.hz:p.hz-r.hz)<=10000;});
        if(current!=rows.end() && current->indices[0]!=r.indices[0]){
            if(pi==pending.end()){
                if(pending.size()>=101)pending.erase(pending.begin());
                pending.push_back({r.hz,now,r.indices[0],1});return false;
            }
            if(pi->label!=r.indices[0]){*pi={r.hz,now,r.indices[0],1};return false;}
            if(++pi->hits<3)return false;
            r.first=pi->first;r.count=3;pending.erase(pi);
        }else{
            if(pi!=pending.end())pending.erase(pi);
            if(current!=rows.end()){
                r.first=current->first;r.count=current->count+1;
                rows.erase(current);rows.insert(rows.begin(),r);++revision;return true;
            }
        }
''' +s[b:]
s=s.replace('void clear(){rows.clear();','void clear(){rows.clear();pending.clear();')
s=s.replace('RML24_HISTORY_V1\\n','RML24_HISTORY_V2\\n')
s=s.replace("f<<r.first<<' '","f<<r.boot<<' '<<r.first<<' '")
s=s.replace('if(!std::getline(f,line)||line!="RML24_HISTORY_V1")','if(!std::getline(f,line)||(line!="RML24_HISTORY_V1" && line!="RML24_HISTORY_V2"))')
s=s.replace('        std::vector<SignalRecord> parsed;','        const bool legacy=line=="RML24_HISTORY_V1";\n        std::vector<SignalRecord> parsed;')
s=s.replace('std::istringstream s(line);SignalRecord r;','std::istringstream s(line);SignalRecord r;\n            if(legacy)r.boot="legacy";else if(!(s>>r.boot)){error="HISTORY FILE INVALID";return false;}')
s=s.replace('s>>extra || !r.first ||','s>>extra ||')
s=s.replace('history_time(d.last)', '(d.boot==h.boot_id?history_time(d.last):"PREVIOUS RUN")')
s=s.replace('history_time(d.first)', '(d.boot==h.boot_id?history_time(d.first):"--")')
s=s.replace('"First seen "','"First uptime "').replace('"   last seen "','"   uptime "')
p.write_text(s,encoding='utf-8',newline='\n')
p=root/'candidate/board_package/board_ui_live_rml24_final.cpp';s=p.read_text(encoding='utf-8').replace('static_cast<std::uint64_t>(std::time(nullptr))','ui::history_uptime_seconds()');p.write_text(s,encoding='utf-8',newline='\n')
p=root/'candidate/ui_sw/ui_render.cpp';s=p.read_text(encoding='utf-8');a=s.index('        const std::time_t stamp=');b=s.index('\n    }\n    draw_info_strip',a)
s=s[:a]+'''        char stamp[64];const auto seconds=st.last_observed_epoch;
        std::snprintf(stamp,sizeof(stamp),"UPTIME %02llu:%02llu:%02llu",
            static_cast<unsigned long long>(seconds/3600),
            static_cast<unsigned long long>((seconds/60)%60),
            static_cast<unsigned long long>(seconds%60));
        draw_text_right(c,stamp,1234,544,th.text_secondary,r20);''' +s[b:]
progress='        if(!st.scan_progress.empty()) draw_text(c,st.scan_progress,650,310,th.text_secondary,b20);'
s=s.replace(progress,'');mark='    outline_rect(c, 24, layout::kHeroY0, 1255, layout::kHeroY1, th.outline, 1);';s=s.replace(mark,mark+'\n    '+progress.strip(),1)
p.write_text(s,encoding='utf-8',newline='\n')
print(root)
