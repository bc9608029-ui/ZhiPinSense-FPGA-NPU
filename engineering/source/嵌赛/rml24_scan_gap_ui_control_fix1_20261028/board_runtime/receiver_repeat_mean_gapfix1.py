"""Gap-fix candidate: frozen repeat mean over the bounded-rescan receiver."""
import hashlib,sys
from pathlib import Path
BASE=Path('/root/rml24_standalone_execution_20261027/candidate/rml24_final')
expected={
 'board_runtime/standalone_receiver.py':'4d35cf5e27f26d6c1bc06f2dbf961b139931b0998ca3995ce47685af38058293',
 'runtime/receiver_core.py':'cb529824a80e9fa2aea6aaa31375c8d560f117c36b9644862cb459f6c39cd79a',
 'recovery/candidate_two_dc.py':'e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a'}
def verify_base():
    for rel,sha in expected.items():
        if hashlib.sha256((BASE/rel).read_bytes()).hexdigest()!=sha:raise RuntimeError('Frozen dependency mismatch '+rel)
def main():
    verify_base();sys.path.insert(0,str(BASE/'board_runtime'))
    import standalone_receiver as receiver
    from receiver_core import RecoveredFrame
    from repeat_mean_candidate import preprocess
    original=receiver.recover_frame
    def candidate_recover(raw,recover):
        frame=original(raw,recover)
        tensor=preprocess(frame.tensor);data=tensor.tobytes(order='C')
        return RecoveredFrame(tensor=tensor,tensor_bytes=data,tensor_sha256=hashlib.sha256(data).hexdigest(),
                              metadata=dict(frame.metadata,repeat_average=8.0))
    receiver.recover_frame=candidate_recover
    return receiver.main()
if __name__=='__main__':raise SystemExit(main())
