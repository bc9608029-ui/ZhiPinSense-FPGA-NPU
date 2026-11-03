import numpy as np
import candidate_two_dc as frozen
import adaptive_repeat_recovery as variable

def recover(raw):
 try:
  windows,metadata=frozen.recover(raw)
  return windows,dict(metadata,detected_repeats=8.0,compatibility_original8=1.0)
 except RuntimeError:pass
 candidates=[]
 for count,fn in ((1,variable.recover_1),(2,variable.recover_2),(4,variable.recover_4)):
  try:
   windows,metadata=fn(raw);candidates.append((metadata['tail_reference_relative_error'],count,windows,metadata))
  except RuntimeError:pass
 if not candidates:raise RuntimeError('no supported verified public tail')
 _,count,windows,metadata=min(candidates,key=lambda x:x[0]);mean=windows.mean(axis=0);out=np.tile(mean,(8,1));return out,dict(metadata,detected_repeats=float(count),compatibility_original8=0.0)
