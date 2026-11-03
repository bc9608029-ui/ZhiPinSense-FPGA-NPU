"""Continuous insertion check for the straight, constant-section male rails.

Plate bottom stays above the whole body. Male rails translate only in -X;
all overlap with the body lies in the same straight female slot. Because the
side boundaries are linear in Z, checking male Z endpoints suffices for the
whole cross section. This does not model printer warp or cable interference.
"""
import json
from pathlib import Path
female_z0=189.65;female_z1=196.55
female_bottom=6.7;female_top=3.7
male_z0=190.0;male_z1=196.4
male_bottom=6.0;male_top=3.0
clearances=[]
for z,male_width in [(male_z0,male_bottom),(male_z1,male_top)]:
 female_width=female_bottom+(female_top-female_bottom)*(z-female_z0)/(female_z1-female_z0)
 clearances.append((female_width-male_width)/2)
assert min(clearances)>0
assert male_z0>female_z0
assert 196.35>196.0
x0=-108.00034332
male_right=x0+316-3.5-.35
slot_right=x0-1+316-3.5+1
assert male_right<slot_right
assert x0-1<x0
report=dict(result='PASS_GEOMETRIC_STRAIGHT_INSERTION',
 minimum_horizontal_side_clearance_mm=min(clearances),
 maximum_horizontal_side_clearance_mm=max(clearances),
 bottom_clearance_mm=male_z0-female_z0,
 plate_clearance_mm=.35,end_stop_gap_mm=slot_right-male_right,
 basis='constant X section; linear Z boundaries; lid withdraws only toward negative X',
 limits='No printer deformation, internal equipment, wiring or friction model',
 sampled_boolean='Stopped due to expensive union; not reported as PASS')
p=Path(__file__).resolve().parent/'continuous_slide_clearance.json'
p.write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2))
