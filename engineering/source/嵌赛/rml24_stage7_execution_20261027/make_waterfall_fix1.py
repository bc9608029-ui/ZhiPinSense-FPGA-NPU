from pathlib import Path
import tarfile,hashlib
root=Path(r'E:\嵌赛\rml24_stage7_execution_20261027');fix=root/'waterfall_fix1';(fix/'board_package').mkdir(parents=True,exist_ok=False)
src=Path(r'E:\嵌赛\rml24_final_integration1_work\board_ui_overlay\board_package\board_ui_live_rml24_final.cpp').read_text(encoding='utf-8')
def change(a,b):
 global src
 assert src.count(a)==1,(a,src.count(a));src=src.replace(a,b)
change('#include "ui_render.hpp"','#include "ui_render.hpp"\n#include "waterfall_history.hpp"')
change('        std::int64_t last_stats_ms = now_ms();','        ui::WaterfallHistory waterfall_history;\n        std::int64_t last_stats_ms = now_ms();')
change('            if (pr.status == ui::UnixSocketServer::PollStatus::Error) break;','            if (pr.status == ui::UnixSocketServer::PollStatus::Error) break;\n            if (pr.client_connected) {\n                waterfall_history.clear();\n                std::printf("UI_WATERFALL_RESET reason=producer_connected rows=0\\n");\n                std::fflush(stdout);\n            }')
change('                        latest = ui::map_to_state_rml24_final(po.frame);','''                        latest = ui::map_to_state_rml24_final(po.frame);
                        if (latest.meas.spectrum_valid &&
                            ui::waterfall_advance_on_presence(latest.presence) &&
                            waterfall_history.push(latest.meas.spectrum_dbfs_x4,
                                po.frame.frame_id, static_cast<std::uint64_t>(now_ms()))) {
                            std::printf("UI_WATERFALL_ROW frame=%llu rows=%llu\\n",
                                static_cast<unsigned long long>(po.frame.frame_id),
                                static_cast<unsigned long long>(waterfall_history.size()));
                            std::fflush(stdout);
                        }''')
change('case 1: ui::render_parameters(canvas, pal, display); break;','case 1: ui::render_parameters(canvas, pal, display, &waterfall_history); break;')
(fix/'board_package/board_ui_live_rml24_final.cpp').write_text(src,encoding='utf-8')
p=root/'rml24_final_stage7_board_overlay/base_ui/board_package/unix_socket_server.hpp';s=p.read_text(encoding='utf-8');a='        PollStatus status = PollStatus::Idle;';assert s.count(a)==1;s=s.replace(a,a+'\n        bool client_connected = false;  // fresh stream; reset display-only history')
a='                    client_fd_ = c;';assert s.count(a)==1;s=s.replace(a,a+'\n                    r.client_connected = true;');(fix/'board_package/unix_socket_server.hpp').write_text(s,encoding='utf-8')
with tarfile.open(root/'transfer/waterfall_fix1_patch.tar.gz','w:gz') as t:
 for p in sorted((fix/'board_package').iterdir()):t.add(p,arcname='board_package/'+p.name)
print('UI_ONLY_PATCH_READY',hashlib.sha256((root/'transfer/waterfall_fix1_patch.tar.gz').read_bytes()).hexdigest())