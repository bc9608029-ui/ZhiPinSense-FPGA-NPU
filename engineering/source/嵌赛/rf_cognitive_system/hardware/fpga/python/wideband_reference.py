"""Board-independent orchestration reference for the advanced wideband path.

This module defines the boundary between spectrum discovery and 1024-sample
AMR extraction.  It is not an RTL implementation and does not assume a
specific SDR, DMA, FPGA IP catalogue, or symbol-rate estimator.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from dsp.wideband_discovery import DiscoveryConfig, discover_signals, extract_signal_frame


@dataclass(frozen=True)
class CandidateDescriptor:
    candidate_id: int
    first_bin: int
    last_bin: int
    center_frequency_hz: float
    occupied_bandwidth_hz: float
    integrated_power: float
    estimated_snr_db: float


@dataclass(frozen=True)
class ExtractionRequest:
    candidate_id: int
    center_frequency_hz: float
    occupied_bandwidth_hz: float
    target_sample_rate_hz: float = 128_000.0
    target_length: int = 1024


def describe_candidates(
    iq: np.ndarray,
    sample_rate_hz: float,
    config: DiscoveryConfig,
) -> list[CandidateDescriptor]:
    """Run FFT discovery and return descriptors suitable for a CPU queue."""

    result = discover_signals(iq, sample_rate_hz, config)
    return [CandidateDescriptor(candidate_id=index, **item) for index, item in enumerate(result["detections"])]


def extract_candidate(
    iq: np.ndarray,
    sample_rate_hz: float,
    request: ExtractionRequest,
    *,
    fir_taps: int = 129,
) -> tuple[np.ndarray, dict[str, object]]:
    """Golden NCO/DDC, FIR and rational resampling for one candidate.

    ``fir_taps=129`` is a software-reference default, not a frozen RTL value.
    Symbol-rate estimation remains TODO-SYMBOL-RATE; a 128 ksample/s output is
    only training-equivalent to 8 samples/symbol for a 16 ksymbol/s signal.
    """

    frame, metadata = extract_signal_frame(
        iq,
        sample_rate_hz,
        request.center_frequency_hz,
        request.occupied_bandwidth_hz,
        target_sample_rate=request.target_sample_rate_hz,
        target_length=request.target_length,
        fir_taps=fir_taps,
    )
    metadata.update(
        {
            "candidate_id": request.candidate_id,
            "symbol_rate_status": "TODO-SYMBOL-RATE",
            "request": asdict(request),
        }
    )
    return frame, metadata
