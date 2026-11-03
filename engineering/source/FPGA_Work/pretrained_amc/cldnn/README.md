---
license: mit
tags:
  - signal-processing
  - modulation-classification
  - radioml
  - pytorch
  - dsp
library_name: pytorch
pipeline_tag: audio-classification
spaces:
  - alirezaaminzadeh/radio-modulation-classifier
model-index:
  - name: alirezaaminzadeh/radio-modulation-classifier
    results:
      - task:
          type: audio-classification
          name: Modulation Classification
        dataset:
          name: RadioML 2018.01A
          type: radioml-2018
        metrics:
          - type: accuracy
            value: 0.7903
            name: test_accuracy_all_snr
          - type: accuracy
            value: 0.9365
            name: test_accuracy_snr_gte_0db
          - type: f1
            name: macro_f1_all_snr
            value: 0.7878
          - type: f1
            name: macro_f1_snr_gte_0db
            value: 0.9390
---

# SignalIQ Modulation Classifier

Convolutional LSTM Deep Network (CLDNN) for automatic radio modulation recognition from I/Q samples.

## Model Description

- **Architecture:** Convolutional LSTM Deep Network (CLDNN)
- **Input:** 2 × 1024 float tensor (In-Phase and Quadrature channels)
- **Output:** 11 modulation classes (RadioML 2018.01A)

### Supported Modulations

AM-DSB, AM-SSB, WBFM, QPSK, QAM16, QAM64, 8PSK, BPSK, CPFSK, GFSK, PAM4

## Intended Uses

- RF spectrum monitoring and signal intelligence
- IoT device RF fingerprinting and security
- Educational demonstrations of DSP + deep learning

## Out-of-Scope Uses

- Unauthorized signal interception or surveillance
- Real-time SDR deployment without domain validation
- Modulation types not in the RadioML 2018.01A taxonomy

## Training Data

Training uses the [RadioML 2018.01A](https://www.deepsig.ai/datasets) taxonomy (11 classes, SNR -20 to +30 dB).
When the full pickle is unavailable locally, a **synthetic I/Q generator** matching RadioML modulation
characteristics is used (stratified 70/15/15 split). Re-train with the downloaded dataset for full-benchmark scores.

## Evaluation Results

| Metric | Value |
|--------|-------|
| Test Accuracy (all SNR) | 0.7903 |
| Macro F1 (all SNR) | 0.7878 |
| Accuracy (SNR ≥ 0 dB) | 0.9365 |
| Macro F1 (SNR ≥ 0 dB) | 0.9390 |

## Limitations

- Performance degrades significantly below -10 dB SNR
- QAM16/QAM64 and QPSK are harder classes (lower F1 at low SNR)
- Trained on synthetic channel models when RadioML pickle is unavailable; real-world performance may vary
- Fixed input length of 1024 samples

## Ethical Considerations

This model has dual-use potential in RF classification. It must not be used for
unauthorized interception of communications.

## License

MIT License — see LICENSE file.

## Citation

```bibtex
@misc{signaliq-modulation-classifier-100,
  title={SignalIQ Modulation Classifier},
  author={Aria AI Engineering},
  year={2026},
  publisher={Hugging Face},
  howpublished={\url{https://huggingface.co/alirezaaminzadeh/radio-modulation-classifier}}
}
```

## Related Resources

- **Space:** [Interactive Demo](https://huggingface.co/spaces/alirezaaminzadeh/radio-modulation-classifier)
- **Dataset:** [Sample I/Q Dataset](https://huggingface.co/datasets/alirezaaminzadeh/radioml-2018-samples)
