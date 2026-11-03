"""Temporary low-power coax link probe using libiio 0.26. Restore RF attributes."""
import ctypes as C
import json, time, os
from pathlib import Path
import numpy as np
L=C.CDLL(os.environ.get('LIBIIO_LIBRARY','C:/Windows/System32/libiio.dll' if os.name=='nt' else '/opt/sdr/libiio-0.26/lib/libiio.so.0'))
P=C.c_void_p; S=C.c_char_p; Z=C.c_size_t; B=C.c_bool
def bind(n,r,*a):
    f=getattr(L,n);f.restype=r;f.argtypes=list(a);return f
context=bind('iio_create_context_from_uri',P,S)
destroy_context=bind('iio_context_destroy',None,P)
timeout=bind('iio_context_set_timeout',C.c_int,P,C.c_uint)
finddev=bind('iio_context_find_device',P,P,S)
findch=bind('iio_device_find_channel',P,P,S,B)
readattr=bind('iio_channel_attr_read',C.c_ssize_t,P,S,P,Z)
writeattr=bind('iio_channel_attr_write',C.c_ssize_t,P,S,S)
enable=bind('iio_channel_enable',None,P)
disable=bind('iio_channel_disable',None,P)
isenabled=bind('iio_channel_is_enabled',B,P)
makebuf=bind('iio_device_create_buffer',P,P,Z,B)
destroybuf=bind('iio_buffer_destroy',None,P)
start=bind('iio_buffer_start',P,P)
end=bind('iio_buffer_end',P,P)
step=bind('iio_buffer_step',C.c_ssize_t,P)
push=bind('iio_buffer_push',C.c_ssize_t,P)
refill=bind('iio_buffer_refill',C.c_ssize_t,P)

def scan_usb():
    make=bind('iio_create_scan_context',P,S,C.c_uint)
    scan=make(b'usb',0);assert scan
    get=bind('iio_scan_context_get_info_list',C.c_ssize_t,P,C.POINTER(C.POINTER(P)))
    uri=bind('iio_context_info_get_uri',S,P)
    free=bind('iio_context_info_list_free',None,C.POINTER(P))
    close=bind('iio_scan_context_destroy',None,P)
    entries=C.POINTER(P)()
    try:
        n=get(scan,C.byref(entries));assert n>=0,n
        return [uri(entries[i]).decode() for i in range(n)]
    finally:
        if entries:free(entries)
        close(scan)

class Radio:
    def __init__(self,uri):
        self.uri=uri;self.ctx=context(uri.encode());assert self.ctx,uri
        timeout(self.ctx,5000)
        self.phy=finddev(self.ctx,b'ad9361-phy');self.saved=[];self.buffers=[];self.enabled=[]
        self.rx=findch(self.phy,b'voltage0',False);self.tx=findch(self.phy,b'voltage0',True)
        self.rlo=findch(self.phy,b'altvoltage0',True);self.tlo=findch(self.phy,b'altvoltage1',True)
    def get(self,ch,key):
        v=C.create_string_buffer(256);n=readattr(ch,key.encode(),v,len(v));assert n>=0,(key,n)
        return v.value.decode().strip()
    def set(self,ch,key,value):
        previous=self.get(ch,key)
        if key=='hardwaregain':previous=previous.split()[0]
        self.saved.append((ch,key,previous))
        n=writeattr(ch,key.encode(),str(value).encode());assert n>=0,(key,value,n)
    def config(self):
        self.set(self.tx,'hardwaregain',-60)
        self.set(self.rx,'gain_control_mode','manual');self.set(self.rx,'hardwaregain',35)
        self.set(self.rx,'sampling_frequency',2560000)
        self.set(self.tx,'sampling_frequency',2560000)
        self.set(self.rx,'rf_bandwidth',18000000);self.set(self.tx,'rf_bandwidth',18000000)
        self.set(self.rlo,'frequency',2400000000);self.set(self.tlo,'frequency',2400000000)
    def config_rx(self):
        self.set(self.rx,'gain_control_mode','manual');self.set(self.rx,'hardwaregain',35)
        self.set(self.rx,'sampling_frequency',2560000)
        self.set(self.rx,'rf_bandwidth',18000000);self.set(self.rlo,'frequency',2400000000)
    def buffer(self,tx,n):
        d=finddev(self.ctx,b'cf-ad9361-dds-core-lpc' if tx else b'cf-ad9361-lpc');assert d
        for i in range(2):
            ch=findch(d,('voltage'+str(i)).encode(),tx);assert ch
            old=isenabled(ch);self.enabled.append((ch,old));enable(ch)
        b=makebuf(d,n,tx);assert b,('makebuf',self.uri,tx)
        self.buffers.append(b);assert step(b)==4,('stride',step(b));return b
    def stop(self,b):
        destroybuf(b);self.buffers.remove(b)
    def send(self,z):
        iq=np.empty((len(z),2),dtype='<i2')
        iq[:,0]=np.round(z.real).astype(np.int16)*16
        iq[:,1]=np.round(z.imag).astype(np.int16)*16
        b=self.buffer(True,len(z));assert end(b)-start(b)==iq.nbytes
        C.memmove(start(b),iq.ctypes.data,iq.nbytes);n=push(b);assert n>0,n;return b
    def receive(self,n=65536):
        b=self.buffer(False,n)
        try:
            size=refill(b);assert size>0,size
            iq=np.frombuffer(C.string_at(start(b),size),dtype='<i2').reshape(-1,2).astype(np.float32)
            return iq[:,0]+1j*iq[:,1]
        finally:self.stop(b)
    def close(self):
        for b in self.buffers[::-1]:destroybuf(b)
        self.buffers=[]
        for ch,old in self.enabled[::-1]:
            if old:enable(ch)
            else:disable(ch)
        errors=[]
        for ch,key,value in self.saved[::-1]:
            n=writeattr(ch,key.encode(),value.encode())
            if n<0:errors.append((key,n))
        destroy_context(self.ctx)
        return errors

def main():
    radios=[];report={'purpose':'low_power_cabled_tone_probe','tx_atten_db':-60,'results':[]}
    try:
        for uri in ['usb:1.12.5','usb:1.13.5']:
            r=Radio(uri);radios.append(r);r.config()
        for tx,rx in [radios,radios[::-1]]:
            z=512*np.exp(2j*np.pi*np.arange(16384)*1250/16384)
            b=tx.send(z)
            try:
                time.sleep(.1);y=rx.receive();a=np.abs(np.fft.fft(y-y.mean()));k=int(a.argmax())
                row={'tx':tx.uri,'rx':rx.uri,'peak_frequency_hz':float(np.fft.fftfreq(len(y),1/2560000)[k]),
                     'rms':float(np.sqrt(np.mean(np.abs(y)**2))),
                     'max_component':float(max(np.abs(y.real).max(),np.abs(y.imag).max())),
                     'peak_to_median_fft_db':float(20*np.log10(a[k]/np.median(a)))}
                report['results'].append(row);print(json.dumps(row),flush=True)
            finally:tx.stop(b)
    finally:
        report['restore_errors']=[r.close() for r in radios[::-1]]
        (Path(__file__).parent/'pluto_link_probe_results.json').write_text(json.dumps(report,indent=2))
    return report
if __name__=='__main__':main()
