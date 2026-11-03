"""V1.1 reliability — Optuna static search space.

The V1 search space broke Optuna's fixed-space assumption in two ways: the same
axis names ``lr``/``wd`` were suggested with *different* value domains depending
on the optimizer, and ``augmentation_groups`` was suggested as a list-valued
categorical.  Both make TPE's internal dimensionality unstable across trials.

This file verifies the V1.1 fixes with two tiers:

* **Always run (no optuna needed)** — a recording fake ``trial`` drives the real
  ``sample_v2_optuna`` / ``sample_rml24_optuna`` code paths and asserts that every
  suggested axis name has exactly one value domain, that no list-valued categorical
  is ever suggested, that the decoded augmentation keys round-trip to the frozen
  ``AUG_GROUPS`` contract, and that the decoded params are JSON-serializable.
* **Optuna-gated** — SQLite ``RDBStorage`` persistence + ``load_study`` recovery and
  ``TPESampler(seed=…)`` reproducibility for the first N trials.  These skip
  offline (where optuna is not installed) and run fully on AutoDL.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from training.rml24_pilot import sample_rml24_optuna
from v2.pilot import AUG_GROUPS, _AUG_KEYS, _decode_aug_groups, sample_v2_optuna


class _RecordingTrial:
    """Fake optuna trial: records (name, choice-domain) pairs, returns seeded picks.

    Any list-valued categorical raises immediately, so the ``sample_*`` functions
    are exercised exactly as optuna would call them.
    """

    def __init__(self, rng: np.random.Generator) -> None:
        self._rng = rng
        self.suggested: list[tuple[str, tuple]] = []

    def suggest_categorical(self, name: str, choices: list) -> object:
        for choice in choices:
            assert not isinstance(choice, (list, tuple, dict)), (
                f"list-valued categorical in axis {name!r}")
        self.suggested.append((name, tuple(choices)))
        return choices[int(self._rng.integers(0, len(choices)))]


def _collect_domains(sample_fn, n_trials: int = 128, seed: int = 0) -> dict[str, set]:
    rng = np.random.default_rng(seed)
    domains: dict[str, set] = {}
    for _ in range(n_trials):
        trial = _RecordingTrial(rng)
        sample_fn(trial)
        for name, domain in trial.suggested:
            domains.setdefault(name, set()).add(domain)
    return domains


def _assert_single_domain_per_axis(sample_fn) -> None:
    domains = _collect_domains(sample_fn)
    for name, seen in domains.items():
        assert len(seen) == 1, f"axis {name!r} has multiple value domains: {seen}"


def test_v2_every_axis_has_a_single_value_domain() -> None:
    # The old code suggested `lr` with two domains ([1e-3,3e-4,1e-4] vs [1e-2,3e-3])
    # depending on the optimizer; the static names must never collapse back to that.
    _assert_single_domain_per_axis(sample_v2_optuna)


def test_rml24_every_axis_has_a_single_value_domain() -> None:
    _assert_single_domain_per_axis(sample_rml24_optuna)


def test_no_dynamic_lr_wd_axes() -> None:
    for sample_fn in (sample_v2_optuna, sample_rml24_optuna):
        domains = _collect_domains(sample_fn)
        assert "lr" not in domains
        assert "wd" not in domains
        # Static unique names are present instead.
        assert {"adamw_lr", "adamw_wd", "sgd_lr", "sgd_wd"} <= set(domains)


def test_no_list_valued_categorical() -> None:
    # _RecordingTrial raises on list-valued choices, so simply driving the sampler
    # many times (across all conditional branches) is the assertion.
    for sample_fn in (sample_v2_optuna, sample_rml24_optuna):
        _collect_domains(sample_fn, n_trials=256)


def test_aug_key_decode_matches_aug_groups_contract() -> None:
    assert len(_AUG_KEYS) == len(AUG_GROUPS) == 8
    assert set(_decode_aug_groups(k) for k in _AUG_KEYS) == set(AUG_GROUPS)
    for key in _AUG_KEYS:
        assert _decode_aug_groups(key) in AUG_GROUPS
    # Bijection: every frozen tuple maps back from exactly one key.
    assert len({_decode_aug_groups(k) for k in _AUG_KEYS}) == len(_AUG_KEYS)


def test_decoded_params_are_json_serializable() -> None:
    rng = np.random.default_rng(1)
    for _ in range(64):
        v2, training = sample_v2_optuna(_RecordingTrial(rng))
        json.dumps({"v2": v2, "training": training}, sort_keys=True)
        v2b, training_b = sample_rml24_optuna(_RecordingTrial(rng))
        json.dumps({"v2": v2b, "training": training_b}, sort_keys=True)


def test_decoded_aug_is_a_list_of_strings() -> None:
    rng = np.random.default_rng(2)
    for _ in range(64):
        v2, _ = sample_v2_optuna(_RecordingTrial(rng))
        assert isinstance(v2["augmentation_groups"], list)
        assert all(isinstance(g, str) for g in v2["augmentation_groups"])


# --------------------------------------------------------------------------- #
# Optuna-gated tests (skip offline, run fully on AutoDL).
# --------------------------------------------------------------------------- #

def _optuna() -> object:
    return pytest.importorskip("optuna")


def test_rdbstorage_persist_and_load_study(tmp_path) -> None:
    optuna = _optuna()
    url = f"sqlite:///{tmp_path / 'optuna.db'}"
    storage = optuna.storages.RDBStorage(url)
    study = optuna.create_study(direction="maximize", storage=storage,
                                sampler=optuna.samplers.TPESampler(seed=2026))

    def objective(trial) -> float:
        sample_v2_optuna(trial)
        return float(trial.number)

    study.optimize(objective, n_trials=4)
    loaded = optuna.load_study(study_name=study.study_name, storage=storage)
    assert len(loaded.trials) == 4
    assert [t.params for t in loaded.trials] == [t.params for t in study.trials]


def test_tpe_sampler_reproducible_first_n_trials() -> None:
    optuna = _optuna()

    def run(n_trials: int) -> list:
        def objective(trial) -> float:
            sample_v2_optuna(trial)
            return float(trial.number)

        study = optuna.create_study(direction="maximize",
                                    sampler=optuna.samplers.TPESampler(seed=2026))
        study.optimize(objective, n_trials=n_trials)
        return [t.params for t in study.trials]

    assert run(12) == run(12)


def test_tpe_reproducible_across_rml24_sampler() -> None:
    optuna = _optuna()

    def run(n_trials: int) -> list:
        def objective(trial) -> float:
            sample_rml24_optuna(trial)
            return float(trial.number)

        study = optuna.create_study(direction="maximize",
                                    sampler=optuna.samplers.TPESampler(seed=2027))
        study.optimize(objective, n_trials=n_trials)
        return [t.params for t in study.trials]

    assert run(12) == run(12)


def test_optuna_search_space_has_no_list_valued_categorical_under_real_storage(tmp_path) -> None:
    # End-to-end: the frozen samplers, driven by a real study over a persistent store,
    # must never feed optuna a list-valued categorical (optuna itself rejects them).
    optuna = _optuna()
    url = f"sqlite:///{tmp_path / 'optuna.db'}"
    storage = optuna.storages.RDBStorage(url)
    study = optuna.create_study(direction="maximize", storage=storage,
                                sampler=optuna.samplers.TPESampler(seed=2026))

    def objective(trial) -> float:
        sample_v2_optuna(trial)
        return float(trial.number)

    study.optimize(objective, n_trials=32)
    assert len(study.trials) == 32
