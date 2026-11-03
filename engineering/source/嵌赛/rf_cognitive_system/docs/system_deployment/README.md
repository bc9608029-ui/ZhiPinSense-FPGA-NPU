# FPGA-NPU system deployment preparation

This directory converts the frozen TimePowerPhase research result into an
implementable, testable system plan. It contains no claim of completed FPGA,
NPU or SDR measurements.

- [Algorithm diagnosis](algorithm_diagnosis.md)
- [FPGA data path](fpga_datapath.md)
- [RTL plan](rtl_plan.md)
- [NPU deployment](npu_deployment.md)
- [Competition technical route](competition_technical_route.md)
- Machine-readable interface: `configs/deployment_contract.yaml`
- Reproducible export: `python -m scripts.export_deployment_candidate`
- Bit-exact feature reference: `deployment/fixed_point_frontend.py`

The Baseline V1 and QAM-Aware V2 frozen files are inputs to this work and must
not be edited. Every device-specific item that cannot be verified without the
board/toolchain is marked `TODO-HARDWARE` or `TODO-NPU`.
