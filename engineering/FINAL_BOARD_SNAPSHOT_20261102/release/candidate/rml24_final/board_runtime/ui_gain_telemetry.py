import math

def apply_gain_telemetry(result,gain_diagnostic,input_calibration=None):
 value=gain_diagnostic.get('final_gain_db',gain_diagnostic.get('readback_gain_db'))
 if value is None or not math.isfinite(float(value)):raise ValueError('actual RX gain readback unavailable')
 out=dict(result);out['rf_gain_db']=float(value);out['level_mode']='AUTO'
 out['model_scale']=float((input_calibration or {}).get('scale',1.0))
 if not math.isfinite(out['model_scale']) or out['model_scale']<=0:raise ValueError('invalid model input calibration scale')
 return out
