import pathlib,tarfile
r=pathlib.Path(__file__).parent;s=pathlib.Path('E:/嵌赛/rml24_scan_final_prep1_20261027/ui_overlay/board_package/board_ui_live_rml24_final.cpp').read_text(encoding='utf-8')
def change(a,b):
 global s
 assert s.count(a)==1,(a,s.count(a));s=s.replace(a,b)
change('#include "ui_render.hpp"','#include "ui_render.hpp"\n#include "waterfall_history.hpp"')
change('        std::int64_t last_stats_ms = now_ms();','        ui::WaterfallHistory waterfall_history;\n        std::int64_t last_stats_ms = now_ms();')
change('            if (pr.status == ui::UnixSocketServer::PollStatus::Error) break;','''            if (pr.status == ui::UnixSocketServer::PollStatus::Error) break;
            if (pr.client_connected) {
                waterfall_history.clear();
                std::printf("UI_WATERFALL_RESET reason=producer_connected rows=0\\n");
                std::fflush(stdout);
            }''')
change('                        latest = ui::map_to_state_rml24_final(po.frame);','''                        latest = ui::map_to_state_rml24_final(po.frame);
                        ui::WaterfallHistory::Row spectrum_row{};
                        for (int b = 0; b < ui::kWaterfallBins; ++b)
                            spectrum_row[b] = static_cast<std::int16_t>(latest.meas.spectrum_dbfs_x4[b]);
                        if (latest.meas.spectrum_valid &&
                            ui::waterfall_advance_on_presence(latest.presence) &&
                            waterfall_history.push(spectrum_row.data(),
                                po.frame.frame_id, static_cast<std::uint64_t>(now_ms()))) {
                            std::printf("UI_WATERFALL_ROW frame=%llu rows=%llu\\n",
                                static_cast<unsigned long long>(po.frame.frame_id),
                                static_cast<unsigned long long>(waterfall_history.size()));
                            std::fflush(stdout);
                        }''')
change('case 1: ui::render_parameters(canvas, pal, display); break;','case 1: ui::render_parameters(canvas, pal, display, &waterfall_history); break;')
(r/'fourpage_waterfall.cpp').write_bytes(s.encode('utf-8'))
h=pathlib.Path('E:/嵌赛/rml24_stage7_execution_20261027/waterfall_fix1/board_package/unix_socket_server.hpp')
with tarfile.open(r/'fourpage_waterfall_patch.tar.gz','w:gz') as t:
 t.add(r/'fourpage_waterfall.cpp',arcname='board_package/board_ui_live_rml24_final.cpp');t.add(h,arcname='board_package/unix_socket_server.hpp')
print('DISPLAY_ONLY_PATCH_READY')