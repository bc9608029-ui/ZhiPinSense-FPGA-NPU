import pathlib,csv,json,shutil
p=pathlib.Path(__file__).parent
f=p/'vector_comparison.json'
if f.exists():shutil.copyfile(f,p/'vector_comparison_attempt1_schema_only.json')
a=list(csv.DictReader((p/'source/evidence/expected_core.csv').open()));b=list(csv.DictReader((p/'source/tb/results/rtl_features.csv').open()));keys=['frame_id','sample_index','power','lag_re','lag_im'];bad=[]
for i,(x,y) in enumerate(zip(a,b)):
 if any(int(x[k])!=int(y[k]) for k in keys):bad.append(i)
r={'frames':19,'expected_samples':len(a),'actual_samples':len(b),'compared_fields':keys,'mismatches':len(bad),'pass':len(a)==len(b) and not bad,'note':'Projection required: frozen CSV also contains unrelated INT8 and address columns.'};f.write_text(json.dumps(r,indent=2));print(json.dumps(r));assert r['pass']