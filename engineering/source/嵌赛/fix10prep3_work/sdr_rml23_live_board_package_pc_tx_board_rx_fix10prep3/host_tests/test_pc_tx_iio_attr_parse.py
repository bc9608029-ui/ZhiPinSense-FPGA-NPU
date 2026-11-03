#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_pc_tx_iio_attr_parse.py -- pure-stdlib unittest of fix10_iio_attr.py.

fix10prep3 §4.1: pylibiio returns IIO attribute values as strings with an optional
physical-unit suffix ("2400000000 Hz", "-89.750000 dB").  float() on those raises
ValueError, so this parser is the single source of truth.  It loads the SAME package
module pc_tx_sdr_fix10.py loads, by absolute path, and never touches libiio, so it runs
under any Python 3 (WSL host-side).
"""

import importlib.util
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD_PATH = os.path.normpath(os.path.join(_HERE, "..", "host_tools",
                                          "fix10_iio_attr.py"))

_spec = importlib.util.spec_from_file_location("fix10_iio_attr", _MOD_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load fix10_iio_attr.py at %s" % _MOD_PATH)
iio_attr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(iio_attr)


class TestParseIioNumericAttr(unittest.TestCase):
    def test_bare_value(self):
        self.assertEqual(iio_attr.parse_iio_numeric_attr("2048"), 2048.0)

    def test_negative_bare(self):
        self.assertEqual(iio_attr.parse_iio_numeric_attr("-40.0"), -40.0)

    def test_dB_suffix(self):
        self.assertEqual(iio_attr.parse_iio_numeric_attr("-89.75 dB"), -89.75)

    def test_Hz_suffix(self):
        self.assertEqual(iio_attr.parse_iio_numeric_attr("2400000000 Hz"), 2400000000.0)

    def test_leading_trailing_whitespace(self):
        self.assertEqual(iio_attr.parse_iio_numeric_attr("   2048   "), 2048.0)

    def test_scientific(self):
        self.assertEqual(iio_attr.parse_iio_numeric_attr("2.56e6"), 2560000.0)

    def test_scientific_with_suffix(self):
        self.assertEqual(iio_attr.parse_iio_numeric_attr("1.0e-3 dB"), 0.001)

    def test_decimal_dot(self):
        self.assertEqual(iio_attr.parse_iio_numeric_attr("2048."), 2048.0)

    def test_plus_sign(self):
        self.assertEqual(iio_attr.parse_iio_numeric_attr("+12.5"), 12.5)

    def test_bytes_input(self):
        self.assertEqual(iio_attr.parse_iio_numeric_attr(b"2048 Hz"), 2048.0)

    def test_malformed_trailing_text_rejected(self):
        with self.assertRaises(iio_attr.IioAttrParseError):
            iio_attr.parse_iio_numeric_attr("-10 dB trailing")

    def test_non_numeric_rejected(self):
        with self.assertRaises(iio_attr.IioAttrParseError):
            iio_attr.parse_iio_numeric_attr("abc")

    def test_empty_rejected(self):
        with self.assertRaises(iio_attr.IioAttrParseError):
            iio_attr.parse_iio_numeric_attr("")

    def test_nan_rejected(self):
        with self.assertRaises(iio_attr.IioAttrParseError):
            iio_attr.parse_iio_numeric_attr("NaN")

    def test_inf_rejected(self):
        with self.assertRaises(iio_attr.IioAttrParseError):
            iio_attr.parse_iio_numeric_attr("inf")


if __name__ == "__main__":
    unittest.main(verbosity=2)
