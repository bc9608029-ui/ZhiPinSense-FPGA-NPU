from pathlib import Path
import hashlib

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/'candidate'
def change(rel, old, new):
    p=C/rel;s=p.read_text(encoding='utf-8');assert old in s,(rel,old[:100]);p.write_text(s.replace(old,new),encoding='utf-8',newline='\n')

runtime='rml24_final/runtime/'
board='rml24_final/board_runtime/'
change(runtime+'standalone_control.py',"['FIXED', 'BAND_SCAN']","['FIXED', 'BAND_SCAN', 'CONTINUOUS_SCAN']")
change(runtime+'ui_event.py','{"FIXED", "BAND SCAN"}','{"FIXED", "BAND SCAN", "CONTINUOUS SCAN"}')
rx=board+'standalone_receiver.py'
change(rx,'from scan_lock_policy import LockHysteresis','from scan_lock_policy import LockHysteresis\nfrom continuous_sweep import ContinuousSweep')
change(rx,"choices=['FIXED','BAND_SCAN']","choices=['FIXED','BAND_SCAN','CONTINUOUS_SCAN']")
change(rx,'    started=time.monotonic();','    sweep=ContinuousSweep()\n    started=time.monotonic();')
change(rx,'            lock_policy.reset()\n            s=ctl.snapshot();','            lock_policy.reset()\n            sweep.reset()\n            s=ctl.snapshot();')
change(rx,"                else:\n                    state('ACQUIRING')", """                elif s['mode']=='CONTINUOUS_SCAN':
                    state('ACQUIRING')
                    config=ScanConfig(s['start_hz'],s['stop_hz'],s['step_hz'])
                    raw,center,capture_ns,step=sweep.probe(
                        config.lo_frequencies(),lo,
                        lambda:np.asarray(radio.receive(65536)),
                        lambda z:detect_public_training(z,public.train),checkpoint,
                        s['start_hz'],s['stop_hz'])
                    steps.append(step)
                    ctl.update(actual_lo_hz=lo.current_hz,scan_index=step['scan_index'],
                               scan_points=step['scan_points'],sweep_cycle=step['sweep_cycle'])
                else:
                    state('ACQUIRING')""")
change(rx,"work_mode='BAND SCAN' if s['mode']=='BAND_SCAN' else 'FIXED'", "work_mode={'FIXED':'FIXED','BAND_SCAN':'BAND SCAN',\n                                        'CONTINUOUS_SCAN':'CONTINUOUS SCAN'}[s['mode']]")
sha=hashlib.sha256((C/rx).read_bytes()).hexdigest()
change(board+'receiver_repeat_mean_gapfix1.py','4d35cf5e27f26d6c1bc06f2dbf961b139931b0998ca3995ce47685af38058293',sha)

# Three mode tokens and UI labels. Legacy BandScan token is kept wire-compatible.
change('board_package/mode_control.hpp','Fixed, AutoLock, BandScan','Fixed, AutoLock, BandScan, ContinuousScan')
change('board_package/mode_control.hpp','case ModeKind::BandScan: return "BAND SCAN";', 'case ModeKind::ContinuousScan: return "SWEEP";\n        case ModeKind::BandScan: return "SEARCH LOCK";')
change('board_package/mode_control.hpp','case ModeKind::BandScan: return "BAND_SCAN";', 'case ModeKind::ContinuousScan: return "CONTINUOUS_SCAN";\n        case ModeKind::BandScan: return "BAND_SCAN";')
change('board_package/mode_control.hpp','    if (tok == "FIXED")', '    if (tok == "CONTINUOUS_SCAN" || tok == "CONTINUOUS SCAN" || tok == "SWEEP") { out = ModeKind::ContinuousScan; return true; }\n    if (tok == "SEARCH LOCK" || tok == "BAND SCAN") { out = ModeKind::BandScan; return true; }\n    if (tok == "FIXED")')
change('board_package/result_frame_v2_parse.hpp','work_mode != "BAND_SCAN")','work_mode != "BAND_SCAN" && work_mode != "CONTINUOUS_SCAN")')
change('board_package/touch_mode_control.hpp','button <= ui::mode_ui::kBtnBandScan','button <= ui::mode_ui::kBtnSweep')
change('board_package/touch_mode_control.hpp','case ui::mode_ui::kBtnBandScan: return mode_ctl::ModeKind::BandScan;', 'case ui::mode_ui::kBtnSweep: return mode_ctl::ModeKind::ContinuousScan;\n            case ui::mode_ui::kBtnBandScan: return mode_ctl::ModeKind::BandScan;')
change('board_package/frequency_control.hpp',"if(!out.empty() && out.back()=='.') out.pop_back(); return out;", "if(!out.empty() && out.back()=='.') { out.pop_back(); }\n        return out;")
change('ui_sw/ui_render.cpp','static void draw_kv_row(', '[[maybe_unused]] static void draw_kv_row(') if 'static void draw_kv_row(' in (C/'ui_sw/ui_render.cpp').read_text(encoding='utf-8') else None
change('ui_sw/ui_render.hpp','constexpr int kModeW = 600;', 'constexpr int kModeW = 394;')
change('ui_sw/ui_render.hpp','constexpr int kModeGap = 30;', 'constexpr int kModeGap = 24;')
change('ui_sw/ui_render.hpp','constexpr int kBtnStart = 2, kBtnStop = 3;', 'constexpr int kBtnSweep = 2;\nconstexpr int kBtnStart = 3, kBtnStop = 4;')
change('ui_sw/ui_render.hpp','constexpr int kBtnCount = 4;', 'constexpr int kBtnCount = 5;')
change('ui_sw/ui_render.hpp','if (i <= kBtnBandScan)', 'if (i <= kBtnSweep)')
change('ui_sw/ui_render.cpp','const int active = (st.work_mode == "BAND SCAN") ? 1 : 0;', 'const int active = (st.work_mode == "SWEEP") ? 2 : ((st.work_mode == "SEARCH LOCK" || st.work_mode == "BAND SCAN") ? 1 : 0);')
change('ui_sw/ui_render.cpp','const char* names[2] = {"FIXED", "BAND SCAN"};', 'const char* names[3] = {"FIXED", "SEARCH LOCK", "SWEEP"};')
change('ui_sw/ui_render.cpp','const char* desc[2] = {"single frequency", "scan, lock and reacquire"};', 'const char* desc[3] = {"listen at one frequency", "find, lock and reacquire", "identify, record, continue"};')
change('ui_sw/ui_render.cpp','for (int i = 0; i < 2; ++i) {\n        int x0, y0, x1, y1;\n        mode_ui::button_rect', 'for (int i = 0; i < 3; ++i) {\n        int x0, y0, x1, y1;\n        mode_ui::button_rect')
change('ui_sw/ui_render.cpp','draw_text(c, desc[i], x0 + 220, y0 + 31, th.text_secondary, r20);','draw_text(c, desc[i], x0 + 20, y0 + 57, th.text_secondary, r20);')
change('ui_sw/ui_render.cpp','draw_text_right(c, tag, x1 - 16, y0 + 31, tag_col, b20);', 'draw_text_right(c, on ? "ON" : (pending && st.requested_mode == names[i] ? "..." : ""), x1 - 14, y0 + 29, tag_col, b20);\n        (void)tag;')
print('Candidate implemented, receiver sha',sha)
