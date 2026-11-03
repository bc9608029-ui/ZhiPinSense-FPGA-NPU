from pathlib import Path
import json
r=Path(r'E:\rml24_gapfix_execution_20261028')
v=dict(status='RMS_CANDIDATE_REJECTED_CONTINUE_NON_DEPLOYMENT_ACCEPTANCE',development_only=True,paired_captures=340,current_mean_correct=339,rms_correct=264,fixes=1,regressions=76,current_first48_correct=48,rms_first48_correct=37,deployed=False,fix2_fixed={'correct':233,'denominator':240,'missing':0},fix2_scan={'correct':237,'denominator':240,'missing':0},promotion='DO_NOT_PROMOTE_FIXED_BELOW_235',next='Evidence audit and UI frequency keypad/control acceptance; FPGA not enabled')
(r/'GMSK_DIAGNOSIS_DECISION.json').write_text(json.dumps(v,indent=2))
