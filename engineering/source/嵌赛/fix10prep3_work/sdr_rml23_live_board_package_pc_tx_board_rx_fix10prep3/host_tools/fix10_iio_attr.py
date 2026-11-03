#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix10_iio_attr.py -- pure-stdlib IIO numeric attribute parser (iio-free).

pylibiio returns IIO channel/device attributes as strings, and the AD9361 / DDS core
often appends a physical-unit suffix ("2400000000 Hz", "-89.750000 dB") or leading /
trailing whitespace, so float("2400000000 Hz") raises ValueError.  This module is the
SINGLE source of truth for parsing those values into a float, so the PC TX service
(pc_tx_sdr_fix10.py) never does float(ch.attrs[name].value) directly, and the parser
can be unit-tested under any Python 3 without libiio.

Parsing rules (fail-closed on malformed input):
  * accept str or bytes (bytes decoded UTF-8 with replacement so a stray byte cannot
    crash the caller);
  * optional surrounding whitespace;
  * a signed decimal / scientific number;
  * an optional trailing unit token of ASCII letters (Hz / dB / kHz / ...) that is
    IGNORED for the numeric magnitude (the read-back checks compare magnitudes, not
    units);
  * anything else raises IioAttrParseError.
"""

import re

__all__ = ["IioAttrParseError", "IIO_NUMERIC_ATTR_RE", "parse_iio_numeric_attr"]

# number: [+-]? (digits[.digits] | .digits | digits) [eE[+-]digits]
# unit:   one optional token of ASCII letters (no digits, no punctuation).
IIO_NUMERIC_ATTR_RE = re.compile(
    r"^\s*([-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?)\s*([A-Za-z]*)\s*$")


class IioAttrParseError(ValueError):
    """A malformed IIO attribute value (not parseable as a number)."""


def parse_iio_numeric_attr(raw, attr=""):
    """Return float(raw) tolerating an optional unit suffix and whitespace.

    `raw` may be str or bytes.  `attr` is the attribute name, used only in the error
    message.
    """
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = str(raw)
    m = IIO_NUMERIC_ATTR_RE.match(text)
    if m is None:
        label = (" '%s'" % attr) if attr else ""
        raise IioAttrParseError(
            "cannot parse IIO attribute%s value %r as a number" % (label, text))
    return float(m.group(1))
