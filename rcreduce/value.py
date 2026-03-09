"""SPICE engineering notation parser and formatter."""

import re

# Suffix table ordered longest-match-first to avoid MEG/MIL vs M ambiguity.
_SUFFIXES = [
    ("MEG", 1e6),
    ("MIL", 25.4e-6),
    ("T", 1e12),
    ("G", 1e9),
    ("K", 1e3),
    ("M", 1e-3),
    ("U", 1e-6),
    ("N", 1e-9),
    ("P", 1e-12),
    ("F", 1e-15),
]

_SUFFIX_PATTERN = re.compile(
    r"^([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*("
    + "|".join(s for s, _ in _SUFFIXES)
    + r")?\s*$",
    re.IGNORECASE,
)

# For formatting: pick the best human-readable suffix.
_FORMAT_TABLE = [
    (1e12, "T"),
    (1e9, "G"),
    (1e6, "MEG"),
    (1e3, "K"),
    (1e0, ""),
    (1e-3, "M"),
    (1e-6, "U"),
    (1e-9, "N"),
    (1e-12, "P"),
    (1e-15, "F"),
]


def parse_value(s: str) -> float:
    """Parse a SPICE value string like '10K', '1.5MEG', '4.7p' into a float."""
    s = s.strip()
    m = _SUFFIX_PATTERN.match(s)
    if not m:
        raise ValueError(f"Cannot parse SPICE value: {s!r}")
    number = float(m.group(1))
    suffix = m.group(2)
    if suffix:
        suffix_upper = suffix.upper()
        for suf, mult in _SUFFIXES:
            if suf == suffix_upper:
                return number * mult
        raise ValueError(f"Unknown suffix: {suffix!r}")
    return number


def format_value(v: float) -> str:
    """Format a float into SPICE engineering notation."""
    if v == 0.0:
        return "0"
    abs_v = abs(v)
    for threshold, suffix in _FORMAT_TABLE:
        if abs_v >= threshold * 0.9999:
            scaled = v / threshold
            # Use integer form if possible
            if scaled == int(scaled):
                return f"{int(scaled)}{suffix}"
            # Up to 4 significant digits
            formatted = f"{scaled:.4g}"
            return f"{formatted}{suffix}"
    # Fallback to exponential
    return f"{v:.6g}"
