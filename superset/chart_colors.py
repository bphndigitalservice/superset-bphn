"""BPHN chart color tokens and per-label mappings for dashboard metadata."""
from __future__ import annotations

# Official brand
BPHN_BLUE = "#192C70"
BPHN_YELLOW = "#FFCB05"
BPHN_BLUE_LIGHT = "#4A6BC7"
BPHN_GOLD = "#E0B504"

# Categorical palette (order matters for multi-series charts).
BPHN_CATEGORICAL = [
    BPHN_BLUE,
    BPHN_YELLOW,
    BPHN_BLUE_LIGHT,
    BPHN_GOLD,
    "#2B4089",
    "#0D9488",
    "#6366F1",
    "#059669",
    "#64748B",
    "#7C3AED",
    "#DC2626",
    "#EC4899",
]

DEFAULT_COLOR_SCHEME = "bphn_brand"

# Pin category / series labels to brand colors (single-metric bar & pie charts).
BPHN_LABEL_COLORS: dict[str, str] = {
    # Anggaran
    "Pagu": BPHN_BLUE,
    "Realisasi": BPHN_YELLOW,
    # Agama
    "Islam": BPHN_BLUE,
    "Protestan": BPHN_YELLOW,
    "Katolik": BPHN_BLUE_LIGHT,
    "Hindu": BPHN_GOLD,
    # Bidang Hukum
    "Perdata": BPHN_BLUE,
    "Pidana": BPHN_YELLOW,
    "TUN": BPHN_BLUE_LIGHT,
}
