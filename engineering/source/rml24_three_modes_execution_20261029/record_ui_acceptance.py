from pathlib import Path
import json
r=Path(r'E:\rml24_three_modes_execution_20261029');v=json.loads((r/'CURRENT_STATUS.json').read_text());v['physical_acceptance']={'three_modes':True,'frequency_2401_back_2400':True,'history_detail_not_live_iq':True,'sweep_progress_after_fix':True,'history_cancel_then_clear':True,'automatic_clear_save_file_header_only_verified':True,'full10_pagination_physical':False};(r/'CURRENT_STATUS.json').write_text(json.dumps(v,indent=2))
