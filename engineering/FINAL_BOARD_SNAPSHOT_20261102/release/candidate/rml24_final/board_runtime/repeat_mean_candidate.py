"""Candidate for the existing public frame with eight identical payload repeats.

Not a transform for eight unrelated data windows. No labels or source IQ used.
"""
import numpy as np
def preprocess(tensor):
    tensor=np.asarray(tensor)
    if tensor.shape!=(8,2,1024) or not np.isfinite(tensor).all():
        raise ValueError('Expected finite [8,2,1024] repeated-payload tensor')
    mean=tensor.mean(axis=0,dtype=np.float64).astype('<f4')
    return np.repeat(mean[None,:,:],8,axis=0)
