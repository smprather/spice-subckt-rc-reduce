"""Tests for SPICE value parser and formatter."""

import pytest
from rcreduce.value import parse_value, format_value


class TestParseValue:
    def test_plain_integer(self):
        assert parse_value("100") == 100.0

    def test_plain_float(self):
        assert parse_value("3.14") == 3.14

    def test_scientific_notation(self):
        assert parse_value("1e-12") == 1e-12

    def test_suffix_k(self):
        assert parse_value("10K") == 10e3

    def test_suffix_k_lowercase(self):
        assert parse_value("10k") == 10e3

    def test_suffix_meg(self):
        assert parse_value("1.5MEG") == 1.5e6

    def test_suffix_meg_lowercase(self):
        assert parse_value("1.5meg") == 1.5e6

    def test_suffix_m_is_milli(self):
        assert parse_value("10M") == pytest.approx(10e-3)

    def test_suffix_p(self):
        assert parse_value("4.7P") == pytest.approx(4.7e-12)

    def test_suffix_n(self):
        assert parse_value("100N") == pytest.approx(100e-9)

    def test_suffix_u(self):
        assert parse_value("1U") == pytest.approx(1e-6)

    def test_suffix_f(self):
        assert parse_value("10F") == pytest.approx(10e-15)

    def test_suffix_t(self):
        assert parse_value("1T") == 1e12

    def test_suffix_g(self):
        assert parse_value("2.5G") == 2.5e9

    def test_suffix_mil(self):
        assert parse_value("1MIL") == pytest.approx(25.4e-6)

    def test_meg_before_m(self):
        """MEG must not be parsed as M + leftover."""
        assert parse_value("1MEG") == 1e6

    def test_mil_before_m(self):
        assert parse_value("2MIL") == pytest.approx(2 * 25.4e-6)

    def test_whitespace(self):
        assert parse_value("  10K  ") == 10e3

    def test_negative_value(self):
        assert parse_value("-5K") == -5e3

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_value("abc")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_value("")

    def test_leading_dot(self):
        assert parse_value(".5K") == 500.0

    def test_scientific_with_suffix(self):
        # Unusual but: 1e2K = 100K = 100000
        assert parse_value("1e2K") == 100e3


class TestFormatValue:
    def test_zero(self):
        assert format_value(0.0) == "0"

    def test_kilo(self):
        assert format_value(10000.0) == "10K"

    def test_pico(self):
        assert format_value(1e-12) == "1P"

    def test_nano(self):
        assert format_value(100e-9) == "100N"

    def test_meg(self):
        assert format_value(1e6) == "1MEG"

    def test_fractional(self):
        result = format_value(4.7e-12)
        assert "4.7" in result
        assert result.endswith("P")

    def test_roundtrip(self):
        """parse(format(v)) should be close to v."""
        for v in [100.0, 1e3, 4.7e-12, 1e6, 0.001, 1e-15]:
            result = parse_value(format_value(v))
            assert result == pytest.approx(v, rel=1e-3)
