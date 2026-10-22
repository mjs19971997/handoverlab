# SPDX-License-Identifier: MIT
"""Link-to-system mapping: one effective SINR from the SINR at several frequencies (optional, since 2.2.0).

Used with fast fading (:mod:`handoverlab.channel.fading`):

* :func:`miesm_qpsk` (mutual-information effective SINR mapping) for radio-link monitoring: the hypothetical PDCCH
  of TS 38.133 Tables 8.1.2.1-1/-2 is QPSK, so the mean bit-wise mutual information of QPSK (the capacity of a
  binary input on a real Gaussian channel per bit) over the PDCCH band is mapped back to the SINR that gives the
  same mutual information on a flat channel; that SINR is compared with Qout and Qin, which are defined on a flat
  (AWGN) channel.
* :func:`capacity_esm` for the delivered rate, which HandoverLab computes with log2(1 + SINR): the SINR whose
  Shannon capacity equals the mean capacity over the carrier.

Both are exact for a flat channel (all points equal) and never exceed the arithmetic mean of the SINR.
"""
from __future__ import annotations

import numpy as np

_GH_X, _GH_W = np.polynomial.hermite.hermgauss(64)
_DB = np.linspace(-40.0, 40.0, 1601)                       # SINR grid of the table [dB]


def bpsk_mi(snr: np.ndarray) -> np.ndarray:
    """Mutual information [bit] of an equiprobable binary input on a real Gaussian channel with SNR ``snr``
    (linear): 1 - E[log2(1 + exp(-L))] with the LLR L ~ N(2 snr, 4 snr), by Gauss-Hermite quadrature.  One QPSK
    component at the complex-symbol SINR ``snr`` sees exactly this channel."""
    s = np.asarray(snr, dtype=float)[..., None]
    z = np.sqrt(2.0) * _GH_X                                                   # standard normal nodes
    llr = 2.0 * s + 2.0 * np.sqrt(s) * z
    f = np.logaddexp(0.0, -llr) / np.log(2.0)
    return 1.0 - (f * _GH_W).sum(axis=-1) / np.sqrt(np.pi)


_MI = bpsk_mi(10.0 ** (_DB / 10.0))
_n = int(np.argmax(np.diff(_MI) <= 0.0)) + 1 if (np.diff(_MI) <= 0.0).any() else len(_DB)
_DB, _MI = _DB[:_n], _MI[:_n]                              # strictly increasing part (QPSK saturates near 18 dB)
QPSK_CAP_DB = float(_DB[-1])


def miesm_qpsk(sinr: np.ndarray, axis: int = -1) -> np.ndarray:
    """Effective SINR (linear) of QPSK over the points along ``axis`` (linear SINR values).  Above about 18 dB
    the mutual information of QPSK is 1 to double precision, so the result is capped there (``QPSK_CAP_DB``)."""
    db = 10.0 * np.log10(np.maximum(np.asarray(sinr, dtype=float), 1e-30))
    mi = np.interp(np.clip(db, _DB[0], _DB[-1]), _DB, _MI).mean(axis=axis)
    return 10.0 ** (np.interp(mi, _MI, _DB) / 10.0)


def capacity_esm(sinr: np.ndarray, axis: int = -1) -> np.ndarray:
    """Effective SINR (linear) with the same Shannon capacity as the mean over the points along ``axis``."""
    return np.exp2(np.log2(1.0 + np.maximum(np.asarray(sinr, dtype=float), 0.0)).mean(axis=axis)) - 1.0
