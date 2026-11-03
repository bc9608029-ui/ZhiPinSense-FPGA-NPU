from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];C=ROOT/'candidate'
def change(rel,old,new):
    p=C/rel;s=p.read_text(encoding='utf-8');assert old in s,(rel,old[:90]);p.write_text(s.replace(old,new),encoding='utf-8',newline='\n')
f='board_package/board_ui_live_rml24_final.cpp'
change(f,'#include "frequency_control.hpp"','#include "frequency_control.hpp"\n#include "../ui_sw/signal_history.hpp"')
change(f,'        const std::string run_id =', '''        ui::SignalHistory signal_history;
        ui::history_ui::Window history_window;
        const std::string history_path=board::get_opt(argc,argv,"--history-file","");
        signal_history.load(history_path);
        bool history_redraw=false;
        std::int64_t history_saved_ms=0;
        std::uint64_t history_saved_revision=0;
        const std::string run_id =''')
change(f,'                        latest = ui::map_to_state_rml24_final(po.frame);','''                        latest = ui::map_to_state_rml24_final(po.frame);
                        signal_history.observe(latest,static_cast<std::uint64_t>(std::time(nullptr)));''')
change(f,'                            touch_nav.on_sample(s.touching, s.point, tnow);','''                            const bool history_was_open=history_window.open;
                            const bool history_changed=history_window.sample(s.touching,s.point.x,s.point.y,
                                s.point.valid,touch_nav.active_page()==0,signal_history);
                            if(history_changed){
                                history_redraw=true;
                                if(!history_path.empty() && !signal_history.save(history_path))
                                    std::printf("UI_HISTORY error=%s\\n",signal_history.error.c_str());
                            }
                            if(history_was_open || history_window.open) continue;
                            touch_nav.on_sample(s.touching, s.point, tnow);''')
# Since the history modal consumes complete sequences, mode/keypad navigation
# never sees their press or release. Opening occurs only on a main-page button.
change(f,'            const std::string frequency_key =','''            if(tnow-history_saved_ms>=5000 && history_saved_revision!=signal_history.revision){
                if(!history_path.empty() && !signal_history.save(history_path))
                    std::printf("UI_HISTORY error=%s\\n",signal_history.error.c_str());
                history_saved_revision=signal_history.revision;history_saved_ms=tnow;
            }
            const std::string frequency_key =''')
change(f,'if (!headless && flip_sched.should_submit(display, page, tnow)) {','if (!headless && (history_redraw || flip_sched.should_submit(display, page, tnow))) {')
change(f,'                const int back = front ^ 1;\n                if (!fb.submit_frame(back, stage, frame_px)) return 10;', '''                if(page==0) ui::history_ui::render(canvas,pal,signal_history,history_window);
                history_redraw=false;
                const int back = front ^ 1;
                if (!fb.submit_frame(back, stage, frame_px)) return 10;''')
change(f,'        print_control_result(','''        if(!history_path.empty() && !signal_history.save(history_path))
            std::printf("UI_HISTORY error=%s\\n",signal_history.error.c_str());
        print_control_result(''')
change(f,'display.work_mode != "BAND SCAN"','display.work_mode != "SEARCH LOCK" && display.work_mode != "SWEEP"')

# Compile-compat fix from the actual AC board review, without AC parser changes.
p=C/'ui_sw/ui_render.cpp';s=p.read_text(encoding='utf-8')
s=s.replace('void draw_kv_row(', '[[maybe_unused]] void draw_kv_row(') if '[[maybe_unused]]' not in s else s
p.write_text(s,encoding='utf-8',newline='\n')
print('History event/touch/render/persistence integrated')
