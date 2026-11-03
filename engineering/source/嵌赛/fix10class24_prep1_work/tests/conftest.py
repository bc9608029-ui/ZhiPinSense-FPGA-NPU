"""pytest fixtures for fix10class24-prep1 offline tests.

All temporary files MUST live inside the new working directory
(F:\\嵌赛\\fix10class24_prep1_work) -- never in the system temp dir and never in
the READ-ONLY reference trees (fix10clean2a_*, fix10clean2b_work,
fix10prep3_work, sdr_rml24_npu_deployment_m29).  ``sys.dont_write_bytecode`` is
set before any reference module is imported so no .pyc is written into them.
"""

import importlib.util
import os
import shutil
import sys
import tempfile

import pytest

sys.dont_write_bytecode = True

SCRIPTS = r"F:\嵌赛\fix10class24_prep1_work\scripts"
WORK_DIR = r"F:\嵌赛\fix10class24_prep1_work"
SMOKE_DIR = os.path.join(WORK_DIR, "clean24_smoke")

sys.path.insert(0, SCRIPTS)


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def build_mod():
    """The build script as a module (imports only reconstruct +
    recovered_tensor_1024 from the D2 authority, and the frozen contract)."""
    return _load_module(
        "build_clean24_smoke_d2",
        os.path.join(SCRIPTS, "build_clean24_smoke_d2.py"))


@pytest.fixture(scope="session")
def verify_mod():
    """The roundtrip verifier as a module (torch, frozen checkpoint 96cd25f8...)."""
    return _load_module(
        "verify_clean24_smoke_roundtrip",
        os.path.join(SCRIPTS, "verify_clean24_smoke_roundtrip.py"))


@pytest.fixture(scope="session")
def work_smoke():
    assert os.path.isdir(SMOKE_DIR), "build clean24_smoke first: %s" % SMOKE_DIR
    return SMOKE_DIR


@pytest.fixture()
def tmp_work():
    """A fresh temp directory INSIDE the new working directory."""
    base = os.path.join(WORK_DIR, "tests", ".pytest_tmp")
    os.makedirs(base, exist_ok=True)
    d = tempfile.mkdtemp(prefix="t_", dir=base)
    yield d
    shutil.rmtree(d, ignore_errors=True)
