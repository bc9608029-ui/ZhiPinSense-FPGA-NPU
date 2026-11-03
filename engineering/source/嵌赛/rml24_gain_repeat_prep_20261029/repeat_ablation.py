"""Same-capture averaging comparison; not a changed transmit frame experiment."""
import numpy as np

def average_first(tensor, count):
    x=np.asarray(tensor)
    if count not in (1,2,4,8) or x.shape!=(8,2,1024) or not np.isfinite(x).all():
        raise ValueError('finite unaveraged [8,2,1024] and N in 1/2/4/8 required')
    mean=x[:count].mean(axis=0,dtype=np.float64).astype('<f4')
    return np.repeat(mean[None],8,axis=0)

def validate_unaveraged_provenance(metadata):
    if metadata.get('stage')!='RECOVERED_BEFORE_REPEAT_MEAN' or metadata.get('repeat_average_applied') is not False:
        raise ValueError('explicit pre-average provenance required; do not infer from tensor shape')

if __name__=='__main__':
    x=np.random.default_rng(1).normal(size=(8,2,1024)).astype('<f4')
    for n in (1,2,4,8):
        y=average_first(x,n)
        assert y.shape==(8,2,1024)
        np.testing.assert_array_equal(y[0],x[:n].mean(axis=0,dtype=np.float64).astype('<f4'))
        np.testing.assert_array_equal(y[0],y[7])
    try:validate_unaveraged_provenance({'repeat_average_applied':True})
    except ValueError:pass
    else:raise AssertionError('averaged input accepted')
    print('REPEAT_ABLATION_SELFTEST PASS; synthetic only, no NPU or RF')
