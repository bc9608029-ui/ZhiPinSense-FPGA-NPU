"""Isolated diagnostic shim, never installed into the original legacy tree."""
import importlib.util,json,os
spec=importlib.util.spec_from_file_location('original_pluto_probe','/root/amr_rescue_20261025/pluto_link_probe.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
scan_usb=original.scan_usb
class Radio(original.Radio):
    def config_rx(self):
        super().config_rx()
        keys=['bb_dc_offset_tracking_en','rf_dc_offset_tracking_en']
        before={k:self.get(self.rx,k) for k in keys}
        arm=os.environ.get('RML_DC_DIAGNOSTIC_ARM','DEFAULT')
        if arm not in ['DEFAULT','BB_OFF','BOTH_OFF']:raise ValueError('Unknown diagnostic arm')
        if arm in ['BB_OFF','BOTH_OFF']:self.set(self.rx,keys[0],0)
        if arm=='BOTH_OFF':self.set(self.rx,keys[1],0)
        after={k:self.get(self.rx,k) for k in keys}
        if any(v not in ['0','1'] for v in before.values()):raise RuntimeError('Unexpected tracking attribute format')
        if arm in ['BB_OFF','BOTH_OFF'] and after[keys[0]]!='0':raise RuntimeError('BB tracking readback mismatch')
        if arm=='BOTH_OFF' and after[keys[1]]!='0':raise RuntimeError('RF tracking readback mismatch')
        print('DC_DIAGNOSTIC '+json.dumps(dict(arm=arm,before=before,applied=after)),flush=True)
