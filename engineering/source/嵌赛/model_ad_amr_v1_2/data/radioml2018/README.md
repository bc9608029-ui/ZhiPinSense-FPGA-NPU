# RadioML2018.01A placement

This source package deliberately does not contain the public dataset.

After extracting the source archive on AutoDL, place the official file at:

`data/radioml2018/GOLD_XYZ_OSC.0001_1024.hdf5`

Keep the supplied `classes.txt` unchanged. Then run:

```bash
bash autodl_ad_amr_v1_1_data_v2/run_data_audit.sh
```

The audit requires 2,555,904 samples, shape `[N,1024,2]`, 24 one-hot labels,
26 SNR strata per class (`-20,-18,...,30`), and 4,096 samples per class/SNR
stratum. It records the
HDF5 SHA-256 and creates deterministic split indices. A renamed archive, `.tar.gz`,
or incomplete extraction is not accepted; the actual `.hdf5` file is required.
