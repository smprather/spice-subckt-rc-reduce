"""Tests for SPICE file parser."""

import pytest
from pathlib import Path
from rcreduce.parser import parse_file, write_file, _extract_rc_info

TESTDATA = Path(__file__).parent.parent / "testdata"


class TestParseFile:
    def test_simple_rc_chain(self):
        sf = parse_file(TESTDATA / "simple_rc_chain.subckt")
        assert len(sf.subcircuits) == 1
        subckt = sf.subcircuits[0]
        assert subckt.name == "simple_rc_chain"
        assert subckt.ports == ["port1", "port2"]
        assert len(subckt.elements) == 5  # R1, C1, R2, C2, R3

    def test_element_types(self):
        sf = parse_file(TESTDATA / "simple_rc_chain.subckt")
        subckt = sf.subcircuits[0]
        types = [e.element_type for e in subckt.elements]
        assert types == ["R", "C", "R", "C", "R"]

    def test_element_values(self):
        sf = parse_file(TESTDATA / "simple_rc_chain.subckt")
        subckt = sf.subcircuits[0]
        r1 = subckt.elements[0]
        assert r1.name == "R1"
        assert r1.value == 100.0
        assert r1.nodes == ["port1", "n1"]

    def test_rc_pi(self):
        sf = parse_file(TESTDATA / "rc_pi.subckt")
        subckt = sf.subcircuits[0]
        assert subckt.name == "rc_pi"
        assert subckt.ports == ["in", "out"]
        assert len(subckt.elements) == 5

    def test_passthrough_elements(self):
        sf = parse_file(TESTDATA / "passthrough.subckt")
        subckt = sf.subcircuits[0]
        # Should have M1, M2, R1, C1, R2, Xbuf, C2
        assert len(subckt.elements) == 7
        m1 = subckt.elements[0]
        assert m1.element_type == "M"
        assert m1.value is None  # passthrough

    def test_star_network(self):
        sf = parse_file(TESTDATA / "rc_star.subckt")
        subckt = sf.subcircuits[0]
        assert subckt.ports == ["p1", "p2", "p3"]
        assert len(subckt.elements) == 4  # R1, R2, R3, C1

    def test_large_mesh(self):
        sf = parse_file(TESTDATA / "large_mesh.subckt")
        subckt = sf.subcircuits[0]
        assert subckt.name == "large_mesh"
        assert len(subckt.ports) == 4
        # Should have many elements
        assert len(subckt.elements) > 100


class TestModelParamFormat:
    def test_r_with_model_and_params(self):
        tokens = ["R6", "n1", "n2", "res_mod", "R=1125.3", "TC1=0.0001", "TC2=0.0000006"]
        info = _extract_rc_info("R", tokens)
        assert info is not None
        assert info.value == pytest.approx(1125.3)
        assert info.model == "res_mod"
        assert info.params == {"TC1": "0.0001", "TC2": "0.0000006"}

    def test_c_with_model_and_params(self):
        tokens = ["C1", "n1", "n2", "cap_mod", "C=2.5P"]
        info = _extract_rc_info("C", tokens)
        assert info is not None
        assert info.value == pytest.approx(2.5e-12)
        assert info.model == "cap_mod"

    def test_simple_value_still_works(self):
        tokens = ["R1", "n1", "n2", "100"]
        info = _extract_rc_info("R", tokens)
        assert info is not None
        assert info.value == pytest.approx(100.0)
        assert info.model == ""

    def test_simple_value_with_trailing_params(self):
        tokens = ["R1", "n1", "n2", "100", "TC1=0.001"]
        info = _extract_rc_info("R", tokens)
        assert info is not None
        assert info.value == pytest.approx(100.0)
        assert info.params == {"TC1": "0.001"}

    def test_no_value_returns_none(self):
        tokens = ["R1", "n1", "n2", "res_mod", "TC1=0.0001"]
        info = _extract_rc_info("R", tokens)
        assert info is None

    def test_model_param_file(self, tmp_path):
        subckt = tmp_path / "model_rc.subckt"
        subckt.write_text(
            ".SUBCKT test_model a b\n"
            "R1 a n1 res_mod R=500 TC1=0.001\n"
            "C1 n1 0 cap_mod C=10P\n"
            "R2 n1 b 200\n"
            ".ENDS test_model\n"
        )
        sf = parse_file(subckt)
        subckt_parsed = sf.subcircuits[0]
        assert len(subckt_parsed.elements) == 3
        r1 = subckt_parsed.elements[0]
        assert r1.value == pytest.approx(500.0)
        assert r1.model == "res_mod"
        assert r1.params == {"TC1": "0.001"}
        c1 = subckt_parsed.elements[1]
        assert c1.value == pytest.approx(10e-12)
        assert c1.model == "cap_mod"
        r2 = subckt_parsed.elements[2]
        assert r2.value == pytest.approx(200.0)
        assert r2.model == ""


class TestWriteFile:
    def test_roundtrip(self, tmp_path):
        sf = parse_file(TESTDATA / "simple_rc_chain.subckt")
        out = tmp_path / "out.subckt"
        write_file(sf, out)

        # Re-parse
        sf2 = parse_file(out)
        assert len(sf2.subcircuits) == 1
        assert sf2.subcircuits[0].name == "simple_rc_chain"
        assert sf2.subcircuits[0].ports == ["port1", "port2"]
        assert len(sf2.subcircuits[0].elements) == 5

    def test_passthrough_roundtrip(self, tmp_path):
        sf = parse_file(TESTDATA / "passthrough.subckt")
        out = tmp_path / "out.subckt"
        write_file(sf, out)

        sf2 = parse_file(out)
        subckt = sf2.subcircuits[0]
        assert subckt.ports == ["VDD", "VSS", "IN", "OUT"]
        m1 = subckt.elements[0]
        assert m1.element_type == "M"
        assert "PMOS" in m1.raw_line
