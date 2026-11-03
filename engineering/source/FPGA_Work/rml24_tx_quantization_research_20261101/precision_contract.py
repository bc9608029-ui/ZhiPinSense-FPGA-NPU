import math,numpy as np
REFERENCE_PILOT=48*math.sqrt(2)
def choose_precision(values,nominal_gain_db,min_gain_db=-89,max_gain_db=0):
 x=np.asarray(values)
 if x.size!=2048 or not np.isfinite(x).all():raise ValueError('invalid payload')
 if not min_gain_db<=nominal_gain_db<=max_gain_db:raise ValueError('gain outside supplied hardware bounds')
 peak=max(float(abs(x).max()),1/math.sqrt(2));k_peak=math.floor(.95*2047/(math.sqrt(2)*peak));k_gain=math.floor(48*10**((nominal_gain_db-min_gain_db)/20));k=min(k_peak,k_gain)
 if k<1:raise ValueError('cannot maintain requested magnitude within DAC/gain limits')
 scale=k*math.sqrt(2);gain=round((nominal_gain_db-20*math.log10(k/48))*4)/4
 if not min_gain_db<=gain<=max_gain_db:raise ValueError('compensated gain outside hardware range')
 return dict(scale=scale,gain_db=gain,peak_component=peak*scale,ideal_pilot_mismatch_db=20*math.log10(k/48)+gain-nominal_gain_db,k=k)
