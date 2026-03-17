"""
Heuristic chemical-state / functional-group hints for common XPS core levels.

Notes:
- These are *approximate* reference binding energies (eV) for Al Kα.
- Real values shift with chemical environment, charging, calibration, and fitting model.
- The goal is to provide quick, reasonable *hints* (not authoritative assignments).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChemState:
    core: str   # e.g. "C1s"
    label: str  # e.g. "C–O"
    be: float   # reference binding energy (eV)


# ---- Reference table (common, simplified) ----
# C 1s (typical organics)
_C1S = [
    ChemState("C1s", "C–C / C–H (sp2/sp3)", 284.8),
    ChemState("C1s", "C–N",                285.6),
    ChemState("C1s", "C–O (alcohol/ether)", 286.2),
    ChemState("C1s", "C=O (carbonyl)",      287.8),
    ChemState("C1s", "O–C=O (carboxyl/ester)", 289.0),
    ChemState("C1s", "π–π* shake-up (aromatic)", 291.0),
    ChemState("C1s", "C–F",                288.5),
    ChemState("C1s", "CF2",                290.8),
    ChemState("C1s", "CF3",                292.8),
]

# O 1s (oxides / organics / hydroxyl)
_O1S = [
    ChemState("O1s", "Metal–O (oxide)",     530.0),
    ChemState("O1s", "O in C=O / oxide-defect", 531.2),
    ChemState("O1s", "C–O / OH",            532.5),
    ChemState("O1s", "Adsorbed H2O",        533.5),
]

# N 1s (organic N / doped carbon, simplified)
_N1S = [
    ChemState("N1s", "Pyridinic / imine (=N–)", 398.5),
    ChemState("N1s", "Amine (–NH2/–NH–) / pyrrolic", 399.8),
    ChemState("N1s", "Amide / protonated N",   400.6),
    ChemState("N1s", "Quaternary / graphitic N", 401.0),
    ChemState("N1s", "N-oxide",                402.8),
]

# S 2p (report as chemical families; actual doublet splitting not modeled here)
_S2P = [
    ChemState("S2p", "S2− (sulfide) / thiol / thioether", 163.5),
    ChemState("S2p", "Thiophene / aromatic-S",            164.0),
    ChemState("S2p", "Sulfoxide (S=O)",                   166.0),
    ChemState("S2p", "Sulfone (O=S=O)",                   168.0),
    ChemState("S2p", "Sulfate / sulfonate",               169.0),
]

# F 1s
_F1S = [
    ChemState("F1s", "Metal fluoride (MxFy)", 684.5),
    ChemState("F1s", "C–F",                   688.5),
    ChemState("F1s", "CF2 / CF3",             690.0),
]


CHEM_STATES: dict[str, list[ChemState]] = {
    "C1s": _C1S,
    "O1s": _O1S,
    "N1s": _N1S,
    "S2p": _S2P,
    "F1s": _F1S,
}


def guess_core_from_range(lo: float, hi: float) -> str | None:
    """
    Guess core level from the fit window energy range (eV).
    Returns one of: C1s/O1s/N1s/S2p/F1s or None if unknown.
    """
    lo, hi = (min(lo, hi), max(lo, hi))
    mid = 0.5 * (lo + hi)

    # Wide ranges: use mid-point heuristic
    if 280 <= mid <= 296:
        return "C1s"
    if 525 <= mid <= 540:
        return "O1s"
    if 395 <= mid <= 410:
        return "N1s"
    if 155 <= mid <= 175:
        return "S2p"
    if 680 <= mid <= 695:
        return "F1s"
    return None


def match_chem_states(core: str, be: float, tol_ev: float = 1.0, top_n: int = 2) -> list[tuple[ChemState, float]]:
    """
    Return top_n candidate chemical states for a given core and peak center (be).
    Each item is (state, delta_eV) where delta_eV = be - state.be.
    """
    core = str(core)
    be = float(be)
    tol_ev = max(float(tol_ev), 0.0)
    top_n = max(int(top_n), 1)

    states = CHEM_STATES.get(core, [])
    hits: list[tuple[ChemState, float]] = []
    for st in states:
        d = be - st.be
        if abs(d) <= tol_ev:
            hits.append((st, d))
    hits.sort(key=lambda t: abs(t[1]))
    return hits[:top_n]

