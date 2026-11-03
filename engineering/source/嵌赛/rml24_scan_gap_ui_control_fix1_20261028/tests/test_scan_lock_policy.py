from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from scan_lock_policy import LockHysteresis

def main():
    p=LockHysteresis(5,1.0)
    assert [p.miss(t) for t in (0.0,0.1,0.2,0.3)] == [False]*4
    p.hit()
    assert p.misses == 0
    # Count alone is insufficient while the inter-frame silence is short.
    assert [p.miss(t) for t in (1.0,1.1,1.2,1.3,1.4)] == [False]*5
    assert p.miss(2.01) is True
    p.reset(); assert p.misses == 0
    try: LockHysteresis(0)
    except ValueError: pass
    else: raise AssertionError('zero budget accepted')
    try: LockHysteresis(5,-0.1)
    except ValueError: pass
    else: raise AssertionError('negative hold time accepted')
    print('scan_lock_policy PASS')

if __name__=='__main__': main()

