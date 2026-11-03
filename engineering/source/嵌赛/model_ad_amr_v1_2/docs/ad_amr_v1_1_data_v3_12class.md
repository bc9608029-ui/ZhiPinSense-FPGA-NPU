# AD-AMR V1.1 data-v3 (12 classes)

## Frozen target contract

The target order is exactly:

`OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM`

Input remains `float32 IQ[N,2,1024]`. Only the classifier output width changes
from 10 to 12. The Conv/Relu/Add/ReduceMean/Gemm deployment operator policy is
unchanged.

RadioML2018.01A is used only to pretrain the shared feature trunk on its public
24-class task. The 24-class head is discarded. All twelve final classes use the
same balanced synthetic target generator, so the model cannot solve the target
by detecting a public-vs-synthetic dataset domain.

The legacy CPFSK-to-GFSK teacher alias is disabled. Teacher logits are mapped by
exact class name, which prevents the two newly prepended outputs from shifting
knowledge-distillation targets into the wrong classes. OOK and 4ASK use direct
supervision; no unrelated teacher output is assigned to them.

## AutoDL order

Extract the new source archive into a new directory. Do not overwrite or resume
the old ten-class run.

```bash
cd /root/autodl-tmp/ad_amr_v1_1_data_v3_12class_run
mkdir -p data/radioml2018
ln -s /root/autodl-tmp/datasets/RadioML2018.01A/GOLD_XYZ_OSC.0001_1024.hdf5 \
  data/radioml2018/GOLD_XYZ_OSC.0001_1024.hdf5
bash autodl_ad_amr_v1_1_data_v3_12class/setup_env.sh
bash autodl_ad_amr_v1_1_data_v3_12class/run_data_audit.sh
bash autodl_ad_amr_v1_1_data_v3_12class/run_preflight.sh
```

Stop after preflight and require the exact marker:

`AD_AMR_V1_1_DATA_V3_12CLASS_CUDA_PREFLIGHT_PASS`

Then run public pretraining and the paired pilot:

```bash
nohup bash autodl_ad_amr_v1_1_data_v3_12class/run_public_pretrain.sh \
  > data_v3_public.log 2>&1 &
tail -f data_v3_public.log

nohup bash autodl_ad_amr_v1_1_data_v3_12class/run_pilot.sh \
  > data_v3_pilot.log 2>&1 &
tail -f data_v3_pilot.log
```

Formal two-seed training is allowed only after the pilot prints
`AD_AMR_V1_1_DATA_V3_12CLASS_PILOT_PASS`:

```bash
nohup bash autodl_ad_amr_v1_1_data_v3_12class/run_formal.sh \
  > data_v3_formal.log 2>&1 &
tail -f data_v3_formal.log
```

The formal gate retains every original absolute threshold and additionally
requires OOK and 4ASK rated-SNR accuracy >= 0.75 for each seed. A formal PASS is
still only an NPU candidate: vendor compilation, numeric parity, SDR capture,
latency and board acceptance remain separate gates.

## Hard boundaries

- Never load or resume a ten-class target checkpoint in this twelve-class run.
- Never select hyperparameters on the RadioML public test split or final blind data.
- Do not claim NPU deployability from ONNX operator inspection alone.
- A pilot/formal `NO_GO` is a valid result and must not be bypassed manually.
