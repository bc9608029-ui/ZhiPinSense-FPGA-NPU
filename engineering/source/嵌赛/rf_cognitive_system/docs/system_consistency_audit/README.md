# System Consistency Audit

This audit is derived from the frozen source and effective configuration. It
does not train a model, perform final-blind inference or claim hardware results.

- [Numerical and normalization contract](numerical_contract.md)
- [Formal channel impairment audit](channel_impairment_audit.md)
- [SDR transport feasibility](sdr_transport.md)
- [Wideband discovery golden architecture](wideband_discovery.md)
- Machine-readable contract: `configs/deployment_numerical_contract.yaml`
- Reproducible trace: `python -m scripts.run_system_consistency_audit`
