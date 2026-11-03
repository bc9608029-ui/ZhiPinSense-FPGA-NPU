"""Generate a tiny preview and communication-domain validation figures."""

from __future__ import annotations

import argparse
import json

import numpy as np

from channel.awgn import add_awgn
from channel.fading import multipath_fading
from channel.impairments import carrier_frequency_offset
from datasets.modulation_generator import generate_iq
from training.utils import ensure_output_dirs, load_config, set_seed
from visualization.constellation import plot_constellation
from visualization.iq_plot import plot_before_after, plot_iq_time
from visualization.spectrum import plot_spectrum_and_psd


def generate_preview(config_path: str, save_count: int = 8) -> None:
    config = load_config(config_path)
    seed = int(config.get("seed", 2026))
    set_seed(seed)
    rng = np.random.default_rng(seed)
    signal_config = config["signal"] if "signal" in config else config
    output_paths = ensure_output_dirs(config.get("output_dir", "outputs"))
    records: list[np.ndarray] = []
    metadata: list[dict[str, object]] = []
    for index in range(save_count):
        modulation = signal_config["modulations"][index % len(signal_config["modulations"])]
        iq, info = generate_iq(modulation, signal_config, rng)
        records.append(iq)
        metadata.append(info)
        if index < len(signal_config["modulations"]):
            plot_iq_time(iq[:300], signal_config["sample_rate"], output_paths["figures"] / f"iq_{modulation.lower()}.png", f"{modulation} complex-baseband I/Q")
            stride = signal_config["samples_per_symbol"] if modulation in {"BPSK", "QPSK", "8PSK", "16QAM", "64QAM"} else None
            plot_constellation(
                iq,
                output_paths["figures"] / f"constellation_{modulation.lower()}.png",
                f"{modulation} constellation validation",
                symbol_stride=stride,
                symbol_offset=int(info.get("symbol_center_offset_samples", 0)),
            )
            plot_spectrum_and_psd(iq, signal_config["sample_rate"], output_paths["figures"] / f"spectrum_{modulation.lower()}.png", f"{modulation} spectral validation")

    # This preview is intentionally tiny; training remains on-the-fly.
    np.savez_compressed(output_paths["tables"] / "synthetic_preview.npz", iq=np.stack(records))
    (output_paths["tables"] / "synthetic_preview_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    clean, _ = generate_iq("QPSK", signal_config, np.random.default_rng(seed + 100))
    noisy, _ = add_awgn(clean, 0.0, np.random.default_rng(seed + 101))
    cfo = carrier_frequency_offset(clean, 2_000.0, signal_config["sample_rate"])
    multipath, _ = multipath_fading(clean, 4, 12, np.random.default_rng(seed + 102))
    plot_before_after(clean, noisy, signal_config["sample_rate"], output_paths["figures"] / "compare_awgn.png", "QPSK: clean versus AWGN at 0 dB", ("Clean", "AWGN, target SNR = 0 dB"))
    plot_before_after(clean, cfo, signal_config["sample_rate"], output_paths["figures"] / "compare_cfo.png", "QPSK: carrier-frequency offset", ("No CFO", "CFO = +2 kHz"))
    plot_before_after(clean, multipath, signal_config["sample_rate"], output_paths["figures"] / "compare_multipath.png", "QPSK: multipath channel", ("Direct path", "Four-tap multipath"))
    print(f"Saved {save_count} preview records and validation figures under {output_paths['figures'].parent}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/synthetic.yaml")
    parser.add_argument("--save-count", type=int, default=8)
    args = parser.parse_args()
    generate_preview(args.config, args.save_count)


if __name__ == "__main__":
    main()
