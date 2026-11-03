"""Unified stochastic channel pipeline with domain-randomization metadata."""

from __future__ import annotations

from typing import Any

import numpy as np

from channel.awgn import add_awgn
from channel.fading import multipath_fading, rayleigh_fading, rician_fading
from channel.impairments import (
    add_dc_offset,
    amplitude_scale,
    burst_interference,
    carrier_frequency_offset,
    clip_iq,
    iq_imbalance,
    narrowband_interference,
    phase_noise,
    random_phase_offset,
    sampling_frequency_offset,
)


def _sample_range(value: Any, rng: np.random.Generator, integer: bool = False) -> float | int:
    if isinstance(value, (list, tuple)):
        low, high = value
        if integer:
            return int(rng.integers(int(low), int(high) + 1))
        return float(rng.uniform(float(low), float(high)))
    return int(value) if integer else float(value)


class ChannelPipeline:
    """Apply enabled effects independently, enabling channel-domain randomization."""

    def __init__(self, config: dict[str, Any], sample_rate: float):
        self.config = config
        self.sample_rate = float(sample_rate)

    def _active(self, name: str, rng: np.random.Generator) -> bool:
        item = self.config.get(name, {})
        if not item.get("enabled", False):
            return False
        if not self.config.get("domain_randomization", True):
            return True
        return bool(rng.random() < float(item.get("probability", 1.0)))

    def __call__(
        self,
        iq: np.ndarray,
        rng: np.random.Generator | None = None,
        snr_db: float | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        rng = rng or np.random.default_rng()
        output = np.asarray(iq, dtype=np.complex64).copy()
        metadata: dict[str, Any] = {"effects": []}

        # Rayleigh and Rician are mutually exclusive when both are sampled.
        if self._active("rayleigh", rng):
            output, info = rayleigh_fading(output, rng)
            metadata.update({"rayleigh": info})
            metadata["effects"].append("rayleigh")
        elif self._active("rician", rng):
            cfg = self.config["rician"]
            k_factor = _sample_range(cfg.get("k_factor", [3.0, 10.0]), rng)
            output, info = rician_fading(output, float(k_factor), rng)
            metadata.update({"rician": info})
            metadata["effects"].append("rician")

        if self._active("multipath", rng):
            cfg = self.config["multipath"]
            taps = _sample_range(cfg.get("num_taps", [2, 5]), rng, integer=True)
            max_delay = int(cfg.get("max_delay", 12))
            output, info = multipath_fading(output, int(taps), max_delay, rng)
            metadata["multipath"] = info
            metadata["effects"].append("multipath")

        if self._active("cfo", rng):
            value = _sample_range(self.config["cfo"].get("hz", 0.0), rng)
            output = carrier_frequency_offset(output, float(value), self.sample_rate)
            metadata["cfo_hz"] = value
            metadata["effects"].append("cfo")

        if self._active("phase_offset", rng):
            value = _sample_range(self.config["phase_offset"].get("radians", 0.0), rng)
            output = random_phase_offset(output, float(value))
            metadata["phase_offset_rad"] = value
            metadata["effects"].append("phase_offset")

        if self._active("phase_noise", rng):
            value = _sample_range(self.config["phase_noise"].get("std_rad", 0.001), rng)
            output = phase_noise(output, float(value), rng)
            metadata["phase_noise_std_rad"] = value
            metadata["effects"].append("phase_noise")

        if self._active("sfo", rng):
            value = _sample_range(self.config["sfo"].get("ppm", 0.0), rng)
            output = sampling_frequency_offset(output, float(value))
            metadata["sfo_ppm"] = value
            metadata["effects"].append("sfo")

        if self._active("iq_imbalance", rng):
            cfg = self.config["iq_imbalance"]
            gain = _sample_range(cfg.get("gain_db", 0.0), rng)
            phase = _sample_range(cfg.get("phase_deg", 0.0), rng)
            output = iq_imbalance(output, float(gain), float(phase))
            metadata["iq_imbalance"] = {"gain_db": gain, "phase_deg": phase}
            metadata["effects"].append("iq_imbalance")

        if self._active("dc_offset", rng):
            magnitude = _sample_range(self.config["dc_offset"].get("magnitude", 0.0), rng)
            phase = float(rng.uniform(-np.pi, np.pi))
            output = add_dc_offset(output, float(magnitude), phase)
            metadata["dc_offset"] = {"magnitude": magnitude, "phase_rad": phase}
            metadata["effects"].append("dc_offset")

        if self._active("amplitude_scaling", rng):
            value = _sample_range(self.config["amplitude_scaling"].get("scale", 1.0), rng)
            output = amplitude_scale(output, float(value))
            metadata["amplitude_scale"] = value
            metadata["effects"].append("amplitude_scaling")

        if self._active("clipping", rng):
            level = _sample_range(self.config["clipping"].get("level_rms", 2.0), rng)
            output = clip_iq(output, float(level))
            metadata["clipping_level_rms"] = level
            metadata["effects"].append("clipping")

        # Freeze the desired component reference before independent interference
        # and AWGN are added. Fading/multipath/scaling therefore change absolute
        # noise power while the requested post-channel SNR stays meaningful.
        desired_signal_power = float(np.mean(np.abs(output) ** 2))
        metadata["desired_signal_power_before_interference_noise"] = desired_signal_power

        if self._active("narrowband_interference", rng):
            cfg = self.config["narrowband_interference"]
            sir = _sample_range(cfg.get("sir_db", 15.0), rng)
            frequency = float(rng.uniform(-0.4, 0.4) * self.sample_rate)
            phase = float(rng.uniform(-np.pi, np.pi))
            output = narrowband_interference(
                output, self.sample_rate, float(sir), frequency, phase, reference_power=desired_signal_power
            )
            metadata["narrowband_interference"] = {"sir_db": sir, "frequency_hz": frequency}
            metadata["effects"].append("narrowband_interference")

        if self._active("burst_interference", rng):
            cfg = self.config["burst_interference"]
            sir = _sample_range(cfg.get("sir_db", 10.0), rng)
            duty = _sample_range(cfg.get("duty_cycle", 0.15), rng)
            output, bounds = burst_interference(
                output, float(sir), float(duty), rng, reference_power=desired_signal_power
            )
            metadata["burst_interference"] = {"sir_db": sir, "duty_cycle": duty, "bounds": list(bounds)}
            metadata["effects"].append("burst_interference")

        awgn_enabled = self.config.get("awgn", {}).get("enabled", False)
        if snr_db is not None or (awgn_enabled and self._active("awgn", rng)):
            selected_snr = snr_db
            if selected_snr is None:
                selected_snr = _sample_range(self.config["awgn"].get("snr_db", 20.0), rng)
            output, info = add_awgn(output, float(selected_snr), rng, reference_power=desired_signal_power)
            metadata["awgn"] = info
            metadata["effects"].append("awgn")

        metadata["output_power"] = float(np.mean(np.abs(output) ** 2))
        return output.astype(np.complex64), metadata
