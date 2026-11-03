"""Config-driven RF channel augmentation for the twelve-class robustness effort.

PROVISIONAL — data-v4 experiment scaffold.

Unlike the frozen baseline ``channel/channel_pipeline.py``, this module holds
**no** parameter defaults of its own: every effect range, probability, and domain
definition is read from a config dict (see
``configs/ad_amr_v1_1_data_v4_12class_robust*.yaml``).  That lets the strong-CFO /
deep-multipath / composite-impairment domains be expressed and tuned purely in
YAML.  Ranges are *not* locked until the AutoDL results justify them.

On top of the baseline effect list it adds two experiment-only mechanisms, both
fully config-driven and **inert** when absent (so the frozen core behaviour is
byte-for-byte unchanged when no ``tail`` / ``composite`` block is present):

* **tail** — an effect may carry a ``tail`` sub-block whose parameters override
  the core parameters with probability ``tail.probability`` (conditional on the
  effect already being active).  This expresses "core range + strong tail" (e.g.
  CFO ``[-1200,1200]`` core plus a ``[-2500,2500]`` tail).
* **composite** — an explicit forced-composite branch: with probability
  ``composite.probability`` a fixed set of effects is applied together (bypassing
  their independent probabilities) at the ranges named in ``composite.effects``.

It reuses the baseline impairment primitives (``channel.impairments``,
``channel.fading``, ``channel.awgn``) and preserves the baseline normalization
contract: per-record RMS normalization happens upstream in ``generate_iq``; the
channel never re-normalizes, and a desired-signal power reference is frozen before
interference/AWGN so SNR/SIR stay meaningful.
"""

from __future__ import annotations

import copy
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

# Canonical application order — identical to the baseline ChannelPipeline.
EFFECT_ORDER: tuple[str, ...] = (
    "rayleigh", "rician", "multipath", "cfo", "phase_offset", "phase_noise", "sfo",
    "iq_imbalance", "dc_offset", "amplitude_scaling", "clipping",
    "narrowband_interference", "burst_interference",
)

_KNOWN_EFFECTS = frozenset(EFFECT_ORDER) | {"awgn"}
_RESERVED_KEYS = frozenset({"domain_randomization", "composite"})


def sample_parameter(spec: Any, rng: np.random.Generator, *, integer: bool = False) -> float | int:
    """Sample a config value that is a scalar or a ``[low, high]`` range.

    Fails closed: a missing / malformed value raises rather than falling back to
    a silent default.  A scalar is returned as-is (cast to ``int`` when
    ``integer``); a range is sampled uniformly (integer ranges are inclusive).
    """
    if isinstance(spec, (list, tuple)):
        if len(spec) != 2:
            raise ValueError(f"range spec must be [low, high], got {spec!r}")
        low, high = float(spec[0]), float(spec[1])
        if low > high:
            raise ValueError(f"range low {low} exceeds high {high}")
        if integer:
            return int(rng.integers(int(low), int(high) + 1))
        return float(rng.uniform(low, high))
    return int(spec) if integer else float(spec)


def _validate_effects(config: dict[str, Any]) -> None:
    for name in config:
        if name in _RESERVED_KEYS:
            continue
        if name not in _KNOWN_EFFECTS:
            raise ValueError(
                f"unknown channel effect {name!r}; known effects: {sorted(_KNOWN_EFFECTS)}"
            )
    composite = config.get("composite")
    if composite and composite.get("enabled", False):
        effects = composite.get("effects", {}) or {}
        unknown = set(effects) - _KNOWN_EFFECTS
        if unknown:
            raise ValueError(f"unknown composite effects: {sorted(unknown)}")
        if "awgn" in effects:
            raise ValueError("composite may not force awgn (AWGN is applied separately)")
        if "rayleigh" in effects or "rician" in effects:
            raise ValueError("composite may not force rayleigh/rician (mutually exclusive fading)")


def _resolve_tail(cfg: dict[str, Any], rng: np.random.Generator) -> tuple[dict[str, Any], bool]:
    """Return ``(resolved_cfg, used_tail)`` for an active effect config.

    When ``cfg`` carries a ``tail`` sub-block, its parameter overrides replace the
    core parameters with probability ``tail.probability`` (conditional on the
    effect already being active).  ``used_tail`` is True only when the tail was
    actually sampled, for audit metadata.
    """
    tail = cfg.get("tail")
    if not tail:
        return cfg, False
    if rng.random() < float(tail.get("probability", 0.0)):
        resolved = copy.deepcopy(cfg)
        for key, value in tail.items():
            if key != "probability":
                resolved[key] = copy.deepcopy(value)
        return resolved, True
    return cfg, False


class RobustChannelPipeline:
    """Config-only channel augmentation with domain-randomization metadata."""

    def __init__(self, config: dict[str, Any], sample_rate: float) -> None:
        _validate_effects(config)
        self.config = config
        self.sample_rate = float(sample_rate)

    def _active(self, name: str, rng: np.random.Generator) -> bool:
        item = self.config.get(name)
        if item is None or not item.get("enabled", False):
            return False
        if not self.config.get("domain_randomization", True):
            return True
        return bool(rng.random() < float(item.get("probability", 1.0)))

    def _composite_forced(self, rng: np.random.Generator) -> dict[str, Any]:
        """Return the forced effect spec when the composite branch fires, else ``{}``."""
        cfg = self.config.get("composite")
        if not cfg or not cfg.get("enabled", False):
            return {}
        if not self.config.get("domain_randomization", True):
            return dict(cfg.get("effects", {}))
        if rng.random() < float(cfg.get("probability", 0.0)):
            return dict(cfg.get("effects", {}))
        return {}

    def _resolve_effect(self, name: str, rng: np.random.Generator,
                        forced: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
        """Resolve one effect to ``(config_or_None, used_tail)``.

        Priority: forced composite spec > independent ``_active`` sampling.  Tail is
        resolved only on the independent path (a forced effect uses its composite
        range as-is).  Returns ``(None, False)`` when the effect is inactive.
        """
        if name in forced:
            return dict(forced[name]), False
        item = self.config.get(name)
        if item is None or not item.get("enabled", False):
            return None, False
        if not self.config.get("domain_randomization", True):
            return _resolve_tail(item, rng)
        if rng.random() < float(item.get("probability", 1.0)):
            return _resolve_tail(item, rng)
        return None, False

    def __call__(
        self,
        iq: np.ndarray,
        rng: np.random.Generator | None = None,
        snr_db: float | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        rng = rng or np.random.default_rng()
        output = np.asarray(iq, dtype=np.complex64).copy()
        metadata: dict[str, Any] = {"effects": []}
        forced = self._composite_forced(rng)
        if forced:
            metadata["composite_branch"] = True
            metadata["composite_effects"] = sorted(forced)

        # Rayleigh and Rician are mutually exclusive when both are sampled, and are
        # never part of the composite branch.
        if self._active("rayleigh", rng):
            output, info = rayleigh_fading(output, rng)
            metadata["rayleigh"] = info
            metadata["effects"].append("rayleigh")
        elif self._active("rician", rng):
            k_factor = sample_parameter(self.config["rician"]["k_factor"], rng)
            output, info = rician_fading(output, float(k_factor), rng)
            metadata["rician"] = info
            metadata["effects"].append("rician")

        cfg, tail_used = self._resolve_effect("multipath", rng, forced)
        if cfg is not None:
            taps = sample_parameter(cfg["num_taps"], rng, integer=True)
            max_delay = int(sample_parameter(cfg["max_delay"], rng, integer=True))
            output, info = multipath_fading(output, int(taps), int(max_delay), rng)
            metadata["multipath"] = info
            if tail_used:
                metadata["multipath_tail"] = True
            metadata["effects"].append("multipath")

        cfg, tail_used = self._resolve_effect("cfo", rng, forced)
        if cfg is not None:
            value = sample_parameter(cfg["hz"], rng)
            output = carrier_frequency_offset(output, float(value), self.sample_rate)
            metadata["cfo_hz"] = float(value)
            if tail_used:
                metadata["cfo_tail"] = True
            metadata["effects"].append("cfo")

        cfg, tail_used = self._resolve_effect("phase_offset", rng, forced)
        if cfg is not None:
            value = sample_parameter(cfg["radians"], rng)
            output = random_phase_offset(output, float(value))
            metadata["phase_offset_rad"] = float(value)
            if tail_used:
                metadata["phase_offset_tail"] = True
            metadata["effects"].append("phase_offset")

        cfg, tail_used = self._resolve_effect("phase_noise", rng, forced)
        if cfg is not None:
            value = sample_parameter(cfg["std_rad"], rng)
            output = phase_noise(output, float(value), rng)
            metadata["phase_noise_std_rad"] = float(value)
            if tail_used:
                metadata["phase_noise_tail"] = True
            metadata["effects"].append("phase_noise")

        cfg, tail_used = self._resolve_effect("sfo", rng, forced)
        if cfg is not None:
            value = sample_parameter(cfg["ppm"], rng)
            output = sampling_frequency_offset(output, float(value))
            metadata["sfo_ppm"] = float(value)
            if tail_used:
                metadata["sfo_tail"] = True
            metadata["effects"].append("sfo")

        cfg, tail_used = self._resolve_effect("iq_imbalance", rng, forced)
        if cfg is not None:
            gain = sample_parameter(cfg["gain_db"], rng)
            phase = sample_parameter(cfg["phase_deg"], rng)
            output = iq_imbalance(output, float(gain), float(phase))
            metadata["iq_imbalance"] = {"gain_db": float(gain), "phase_deg": float(phase)}
            if tail_used:
                metadata["iq_imbalance_tail"] = True
            metadata["effects"].append("iq_imbalance")

        cfg, tail_used = self._resolve_effect("dc_offset", rng, forced)
        if cfg is not None:
            magnitude = sample_parameter(cfg["magnitude"], rng)
            phase = float(rng.uniform(-np.pi, np.pi))
            output = add_dc_offset(output, float(magnitude), phase)
            metadata["dc_offset"] = {"magnitude": float(magnitude), "phase_rad": phase}
            if tail_used:
                metadata["dc_offset_tail"] = True
            metadata["effects"].append("dc_offset")

        cfg, tail_used = self._resolve_effect("amplitude_scaling", rng, forced)
        if cfg is not None:
            value = sample_parameter(cfg["scale"], rng)
            output = amplitude_scale(output, float(value))
            metadata["amplitude_scale"] = float(value)
            if tail_used:
                metadata["amplitude_scaling_tail"] = True
            metadata["effects"].append("amplitude_scaling")

        cfg, tail_used = self._resolve_effect("clipping", rng, forced)
        if cfg is not None:
            level = sample_parameter(cfg["level_rms"], rng)
            output = clip_iq(output, float(level))
            metadata["clipping_level_rms"] = float(level)
            if tail_used:
                metadata["clipping_tail"] = True
            metadata["effects"].append("clipping")

        # Freeze the desired component reference before independent interference
        # and AWGN are added (matches baseline semantics).
        desired_signal_power = float(np.mean(np.abs(output) ** 2))
        metadata["desired_signal_power_before_interference_noise"] = desired_signal_power

        cfg, tail_used = self._resolve_effect("narrowband_interference", rng, forced)
        if cfg is not None:
            sir = sample_parameter(cfg["sir_db"], rng)
            frequency = float(rng.uniform(-0.4, 0.4) * self.sample_rate)
            phase = float(rng.uniform(-np.pi, np.pi))
            output = narrowband_interference(
                output, self.sample_rate, float(sir), frequency, phase,
                reference_power=desired_signal_power,
            )
            metadata["narrowband_interference"] = {"sir_db": float(sir), "frequency_hz": frequency}
            metadata["effects"].append("narrowband_interference")

        cfg, tail_used = self._resolve_effect("burst_interference", rng, forced)
        if cfg is not None:
            sir = sample_parameter(cfg["sir_db"], rng)
            duty = sample_parameter(cfg["duty_cycle"], rng)
            output, bounds = burst_interference(
                output, float(sir), float(duty), rng, reference_power=desired_signal_power
            )
            metadata["burst_interference"] = {
                "sir_db": float(sir), "duty_cycle": float(duty), "bounds": list(bounds),
            }
            metadata["effects"].append("burst_interference")

        awgn = self.config.get("awgn", {})
        if snr_db is not None or (awgn.get("enabled", False) and self._active("awgn", rng)):
            selected = snr_db
            if selected is None:
                selected = sample_parameter(awgn["snr_db"], rng)
            output, info = add_awgn(output, float(selected), rng, reference_power=desired_signal_power)
            metadata["awgn"] = info
            metadata["effects"].append("awgn")

        metadata["output_power"] = float(np.mean(np.abs(output) ** 2))
        return output.astype(np.complex64), metadata


def build_domain_config(
    base_channel: dict[str, Any],
    domain_name: str,
    domain_specs: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    """Derive a per-domain channel config from a domain-spec table.

    Every effect is disabled (probability 0) except ``awgn`` and the effects named
    for ``domain_name``, which are enabled at probability 1.0.  This mirrors the
    baseline OOD evaluator's semantics but is driven entirely by ``domain_specs``
    (e.g. the ``robust_domains`` section of the robust YAML).
    """
    specs = domain_specs.get(domain_name)
    if specs is None:
        raise KeyError(
            f"unknown robustness domain {domain_name!r}; known: {sorted(domain_specs)}"
        )
    cfg = copy.deepcopy(base_channel)
    cfg["domain_randomization"] = False
    for name in EFFECT_ORDER:
        cfg.setdefault(name, {})["enabled"] = False
        cfg[name]["probability"] = 0.0
    cfg.setdefault("awgn", {}).update({"enabled": True, "probability": 1.0})
    for name, overrides in specs.items():
        cfg.setdefault(name, {}).update(overrides)
        cfg[name].update({"enabled": True, "probability": 1.0})
    return cfg


__all__ = [
    "EFFECT_ORDER",
    "RobustChannelPipeline",
    "build_domain_config",
    "sample_parameter",
]
