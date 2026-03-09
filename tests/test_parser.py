"""Tests for SPICE file parser."""

import pytest
from pathlib import Path
from rcreduce.parser import parse_file, write_file

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
