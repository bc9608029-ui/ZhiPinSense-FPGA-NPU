"""Write a small fixed-point versus float DSP comparison report."""

from __future__ import annotations

import json

import numpy as np

from datasets.modulation_generator import generate_iq
from dsp.golden_reference import run_golden_comparison
from training.utils import ensure_output_dirs, load_config


def main() -> None:
    config = load_config("configs/synthetic.yaml")
    iq, _ = generate_iq("QPSK", config["signal"], np.random.default_rng(config["seed"]))
    result = run_golden_comparison(iq, config["signal"]["sample_rate"], fft_length=1024)
    path = ensure_output_dirs("outputs")["tables"] / "golden_reference_report.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

