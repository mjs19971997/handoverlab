# SPDX-License-Identifier: MIT
"""NTN against TR 38.821 and TR 38.811 (since 2.0.0): ``handoverlab verify --only ntn``.

N1  link budget: for the S-band LEO downlink cases of TR 38.821 Table 6.1.3.3-1 the slant range and free-space
    path loss of TR 38.811 Eqs. 6.6-2 and 6.6-3 at the 30 degree target elevation, the atmospheric loss of
    Eq. 6.6-8 and the CNR with the margins of Table 6.1.3.2-1 equal the table within 0.1 dB (its rounding);
N2  (since 2.1.0) the satellite beams of the simulator have the tabled 3 dB beamwidth of TR 38.821 Tables
    6.1.1.1-1 and -2 for both S-band apertures (Table 6.1.1.1-4: only the 3 dB beamwidth is used), the antenna
    pattern of TR 38.811 clause 6.4.1 scaled to it has that 3 dB width within 0.0001 degree, and the adjacent beam
    spacing sqrt(3) sin(HPBW / 2) is within 0.0002 of the informative values of Table 6.1.1.1-6 (0.0668 and
    0.1334); until 2.0.0 the width came from the aperture (8.8462 instead of 8.8320 degrees for 1 m);
N3  the orbital speed at 600 km is within 0.5 % of 7.56 km/s (TR 38.821 Table 7.1-1) and the nadir 3 dB
    footprint of the Set-1 S-band beam within 10 % of the informative 50 km of Table 6.1.1.1-1.

The criteria were fixed in a plan before the first run.
"""
from __future__ import annotations

import math

from ..channel.ntn import NtnGeometry, fspl_db, hpbw_deg, ka_from_aperture, orbital_speed, slant_range
from ..scenarios import builtin_scenario

K_BOLTZMANN_DB = -228.6        # dBW/K/Hz, TR 38.821 clause 6.1.3.1
T0 = 290.0

#: TR 38.821 Table 6.1.3.3-1, S-band DL: case -> (altitude km, EIRP dBm, bandwidth MHz, FSPL dB, atmospheric dB, CNR dB)
CASES = {"SC9": (600, 78.8, 30.0, 159.1, 0.1, 6.6), "SC10": (600, 74.0, 10.0, 159.1, 0.1, 6.6),
         "SC14": (1200, 84.8, 30.0, 164.5, 0.1, 7.2), "SC15": (1200, 80.0, 10.0, 164.5, 0.1, 7.2),
         "SC24": (600, 72.8, 30.0, 159.1, 0.1, 0.6), "SC25": (600, 68.0, 10.0, 159.1, 0.1, 0.6),
         "SC29": (1200, 78.8, 30.0, 164.5, 0.1, 1.2), "SC30": (1200, 74.0, 10.0, 164.5, 0.1, 1.2)}
#: Table 6.1.3.2-1: shadowing margin 3 dB for terminals other than VSAT, ionospheric scintillation 2.2 dB
SHADOW_MARGIN_DB, SCINT_DB = 3.0, 2.2
ATM_ZENITH_2GHZ_DB = 0.045       # the value of the NTN card (ntn.atm_zenith_db)


def handheld_gt_db(gain_dbi: float = 0.0, nf_db: float = 7.0, t_ant: float = 290.0) -> float:
    """G/T [dB/K] of the handheld UE of TR 38.821 Table 6.1.1.1-3 (Eq. 6.1.3.1-3)."""
    return gain_dbi - nf_db - 10.0 * math.log10(T0 + (t_ant - T0) * 10.0 ** (-0.1 * nf_db))


def link_budget(h_km: float, eirp_dbm: float, bw_mhz: float, elev_deg: float = 30.0, fc_ghz: float = 2.0):
    """(FSPL, atmospheric loss, CNR) [dB] of an S-band downlink to a handheld UE (TR 38.821 clause 6.1.3)."""
    d = float(slant_range(elev_deg, h_km * 1e3))
    fspl = float(fspl_db(d, fc_ghz))
    atm = ATM_ZENITH_2GHZ_DB / math.sin(math.radians(elev_deg))
    cnr = (eirp_dbm - 30.0 + handheld_gt_db() - K_BOLTZMANN_DB - 10.0 * math.log10(bw_mhz * 1e6) - fspl - atm
           - SHADOW_MARGIN_DB - SCINT_DB)
    return fspl, atm, cnr


def ntn_checks(rep) -> None:
    rep.section("ntn", "NTN against TR 38.821 V16.2.0 and TR 38.811 V15.4.0 (link budget, antenna, orbit)")
    worst = 0.0
    rows = []
    for case, (h, eirp, bw, fspl_t, atm_t, cnr_t) in CASES.items():
        fspl, atm, cnr = link_budget(h, eirp, bw)
        err = max(abs(round(fspl, 1) - fspl_t), abs(round(atm, 1) - atm_t), abs(cnr - cnr_t))
        worst = max(worst, err)
        rows.append("%s %.1f/%.1f/%.2f" % (case, fspl, atm, cnr))
    rep.check("N1: FSPL, atmospheric loss and CNR of 8 S-band LEO cases of Table 6.1.3.3-1 within 0.1 dB",
              worst <= 0.1 + 1e-9, "largest difference %.3f dB; %s" % (worst, "; ".join(rows[:3]) + "; ..."))
    bad = []
    for aperture, tabled, abs_t in ((2.0, 4.4127, 0.0668), (1.0, 8.8320, 0.1334)):
        # the baseline of Table 6.1.1.1-6 for C2/D2: central beam at nadir
        sc = builtin_scenario("ntn-leo600-2ghz").with_overrides({"ntn.aperture_m": aperture,
                                                                  "ntn.centre_elevation_deg": 90.0})
        geom = NtnGeometry(sc)
        hp = hpbw_deg(geom.ka)
        spacing = math.sqrt(3.0) * math.sin(math.radians(geom.hpbw) / 2.0)
        if abs(geom.hpbw - tabled) > 1e-9 or abs(hp - tabled) > 1e-4 or abs(spacing - abs_t) > 2e-4:
            bad.append("%.1f m: beamwidth %.4f, pattern %.4f, spacing %.5f against %.4f, %.4f"
                       % (aperture, geom.hpbw, hp, spacing, tabled, abs_t))
        rows.append("%.1f m %.4f deg, spacing %.5f (aperture alone: %.4f deg)"
                    % (aperture, hp, spacing, hpbw_deg(ka_from_aperture(aperture, 2.0))))
    rep.check("N2: tabled 3 dB beamwidth of the S-band apertures 2 m and 1 m, pattern and beam spacing", not bad,
              "; ".join(bad) if bad else ", ".join(rows[-2:]))
    v = orbital_speed(600e3)
    hp = NtnGeometry(builtin_scenario("ntn-leo600-2ghz")).hpbw
    foot = 2.0 * 600e3 * math.tan(math.radians(hp / 2.0))
    rep.check("N3: orbital speed at 600 km within 0.5 % of 7.56 km/s, nadir footprint within 10 % of 50 km",
              abs(v / 7560.0 - 1.0) <= 0.005 and abs(foot / 50e3 - 1.0) <= 0.10,
              "%.0f m/s; footprint %.1f km" % (v, foot / 1e3))
