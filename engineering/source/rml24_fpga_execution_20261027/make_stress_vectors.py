import pathlib,csv,json
p=pathlib.Path(__file__).parent/'source';rows=list(csv.DictReader((p/'evidence/expected_core.csv').open()));frames=len(rows)//1024
for key,width in [('power',8),('lag_re',9),('lag_im',9)]:
 bits=32 if key=='power' else 33
 (p/'vectors'/('expected_'+key+'.hex')).write_text(''.join(format(int(r[key])&((1<<bits)-1),'0%dx'%width)+'\n' for r in rows))
energy=[sum(int(r['power']) for r in rows[i:i+1024]) for i in range(0,len(rows),1024)];peak=[max(int(r['power']) for r in rows[i:i+1024]) for i in range(0,len(rows),1024)]
(p/'vectors/expected_energy.hex').write_text(''.join(f'{x:011x}\n' for x in energy));(p/'vectors/expected_peak.hex').write_text(''.join(f'{x:08x}\n' for x in peak))
print(json.dumps({'frames':frames,'samples':len(rows),'max_energy':max(energy),'max_peak':max(peak)}))