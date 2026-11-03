import unittest
import numpy as np
from repeat_mean_candidate import preprocess
class Tests(unittest.TestCase):
    def test_clean_identical_repeats_unchanged(self):
        rng=np.random.default_rng(7028)
        x=rng.normal(size=(1,2,1024)).astype('<f4');t=np.repeat(x,8,axis=0)
        self.assertEqual(preprocess(t).tobytes(),t.tobytes())
    def test_noise_reduction_without_source_input(self):
        rng=np.random.default_rng(7029);clean=rng.normal(size=(1,2,1024))
        noisy=(clean+rng.normal(size=(8,2,1024))*.1).astype('<f4')
        before=np.mean((noisy-clean)**2);after=np.mean((preprocess(noisy)-clean)**2)
        self.assertLess(after/before,.16)
    def test_contract(self):
        for shape in [(2,1024),(8,1024,2)]:
            with self.assertRaises(ValueError):preprocess(np.zeros(shape))
        x=np.zeros((8,2,1024));x[0,0,0]=np.nan
        with self.assertRaises(ValueError):preprocess(x)
if __name__=='__main__':unittest.main(verbosity=2)
