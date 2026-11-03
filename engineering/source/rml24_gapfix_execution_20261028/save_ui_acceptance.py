import json
from pathlib import Path
r=Path(r'E:\rml24_gapfix_execution_20261028')
v=dict(physical_user_confirmed={'five_pages_and_live_plots':True,'two_modes_four_fields':True,'keypad_fixed_2401_then_2400_applied':True,'scan_2396_2404_2_applied':True,'step_zero_rejected_previous_preserved':True,'defaults_2395_2405_1_restored':True,'band_scan_fixed_stop_start':True},rf={'fixed':{'correct':233,'total':240,'missing':0},'scan':{'correct':237,'total':240,'missing':0}},rms_candidate='REJECTED_76_DEVELOPMENT_CAPTURE_REGRESSIONS',promotion='DO_NOT_PROMOTE_FIXED_BELOW_235',fpga_extension='NOT_STARTED_MAINCHAIN_NOT_PROMOTED',evidence='ui_acceptance_final.log',note='Physical confirmations are user reports; no fabricated screenshot or per-touch ACK trace.')
(r/'UI_ACCEPTANCE_SUMMARY.json').write_text(json.dumps(v,indent=2))
