import copy,json,subprocess,sys,unittest
from pathlib import Path
from strict_promotion_gate import evaluate
r=Path(__file__).parent;d=r/'gate_test_fixtures';d.mkdir(exist_ok=True)
base=dict(denominator=240,correct=240,missing=0,
          rows=[dict(index=i,label=i%24,pred=i%24,chosen_frame=i,file=str(i)) for i in range(240)])
class Tests(unittest.TestCase):
    def setUp(self):
        self.paths=[d/(n+'.json') for n in ['bf','bs','cf','cs']]
        for p in self.paths:p.write_text(json.dumps(base))
    def decision(self,c):
        self.paths[2].write_text(json.dumps(c));return evaluate(*self.paths)['verdict']
    def test_valid(self):self.assertEqual(self.decision(base),'PROMOTION_CANDIDATE')
    def test_lying_counter(self):
        c=copy.deepcopy(base);c['rows'][0]['pred']=1
        self.assertEqual(self.decision(c),'DO_NOT_PROMOTE')
        args=[sys.executable,str(r/'prep_tools/scripts/promotion_gate.py')]
        for key,path in zip(['baseline-fixed','baseline-scan','candidate-fixed','candidate-scan'],self.paths):args+=['--'+key,str(path)]
        args+=['--out',str(d/'old_gate_counterexample.json')]
        subprocess.run(args,check=False,capture_output=True)
        self.assertEqual(json.loads((d/'old_gate_counterexample.json').read_text())['verdict'],'PROMOTION_CANDIDATE')
    def test_duplicate(self):
        c=copy.deepcopy(base);c['rows'][1]['index']=0;self.assertEqual(self.decision(c),'DO_NOT_PROMOTE')
    def test_missing(self):
        c=copy.deepcopy(base);c['rows'][0].update(pred=-1,chosen_frame=None);c.update(correct=239,missing=1)
        self.assertEqual(self.decision(c),'DO_NOT_PROMOTE')
    def test_regression(self):
        c=copy.deepcopy(base);c['rows'][0]['pred']=1;c['correct']=239
        self.assertEqual(self.decision(c),'DO_NOT_PROMOTE')
if __name__=='__main__':unittest.main(verbosity=2)
