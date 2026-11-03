import unittest
from scoring_core import score
class Tests(unittest.TestCase):
    tx=dict(index=0,file='test',label=3,start_ns=0,end_ns=4000000000)
    def frame(self,t,pred,fid,finite=True):
        return dict(capture_time_ns=t,pred=pred,frame_id=fid,finite=finite)
    def test_first_wrong_later_correct_stays_wrong(self):
        v=score([self.tx],[self.frame(1600000000,2,10),self.frame(2000000000,3,11)],0)[0]
        self.assertFalse(v['correct']);self.assertEqual(v['chosen_frame'],10)
    def test_missing_stays_in_denominator(self):
        v=score([self.tx],[],0)
        self.assertEqual(len(v),1);self.assertFalse(v[0]['correct']);self.assertEqual(v[0]['pred'],-1)
    def test_time_guard_excludes_transition(self):
        v=score([self.tx],[self.frame(1400000000,3,1),self.frame(3800000000,3,2)],0)[0]
        self.assertIsNone(v['chosen_frame'])
    def test_offset_applies_before_selection(self):
        v=score([self.tx],[self.frame(600000000,3,1)],1000000000)[0]
        self.assertTrue(v['correct'])
    def test_invalid_cannot_be_counted_correct(self):
        v=score([self.tx],[self.frame(1600000000,3,1,False)],0)[0]
        self.assertFalse(v['correct'])
if __name__=='__main__':unittest.main(verbosity=2)
