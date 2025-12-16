# shi/plots/njets_xs.py
# coding: utf-8


from __future__ import annotations

import json
import os
import pickle
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import numpy as np
import matplotlib.pyplot as plt

# mplhep is commonly available in CMSSW environments where you used it already
import mplhep as hep


@dataclass
class Interval:
    best: float
    lo: float
    hi: float

    @property
    def err_down(self) -> float:
        return self.best - self.lo if np.isfinite(self.lo) else np.nan

    @property
    def err_up(self) -> float:
        return self.hi - self.best if np.isfinite(self.hi) else np.nan


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)


def _linear_crossing(x1: float, y1: float, x2: float, y2: float, level: float) -> float:
    # y(x) is linear between points (x1,y1) and (x2,y2)
    if y2 == y1:
        return np.nan
    t = (level - y1) / (y2 - y1)
    return x1 + t * (x2 - x1)


def _find_interval_1sigma(x: np.ndarray, y: np.ndarray, best_x: float) -> Interval:
    """
    Find dnll2=1 crossings left/right of best_x using linear interpolation.
    x: scan points
    y: dnll2 values
    """
    # sanitize
    m = np.isfinite(x) & np.isfinite(y)
    x = x[m]
    y = y[m]
    if len(x) < 3:
        return Interval(best=best_x, lo=np.nan, hi=np.nan)

    # sort by x
    order = np.argsort(x)
    x = x[order]
    y = y[order]

    # locate closest index to best_x (best might be from poi_mins)
    i0 = int(np.argmin(np.abs(x - best_x)))

    level = 1.0

    # left crossing
    lo = np.nan
    for i in range(i0, 0, -1):
        y_a, y_b = y[i - 1], y[i]
        if (y_a - level) * (y_b - level) <= 0 and not (y_a == y_b == level):
            lo = _linear_crossing(x[i - 1], y_a, x[i], y_b, level)
            break

    # right crossing
    hi = np.nan
    for i in range(i0, len(x) - 1):
        y_a, y_b = y[i], y[i + 1]
        if (y_a - level) * (y_b - level) <= 0 and not (y_a == y_b == level):
            hi = _linear_crossing(x[i], y_a, x[i + 1], y_b, level)
            break

    return Interval(best=best_x, lo=lo, hi=hi)


def load_merge_npz(npz_path: str, poi_name: str) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Load MergeLikelihoodScan .npz and return:
      x (scan values), dnll2, best-fit poi value

    The DHI MergeLikelihoodScan writes:
      np.savez(..., data=<recarray>, poi_mins=<recarray or structured array>)
    """
    arr = np.load(npz_path, allow_pickle=True)
    data = arr["data"]
    # "data" is a recarray-like with fields: <poi>, nll0, nll, dnll, dnll2, fit_nll
    x = np.array(data[poi_name], dtype=float)
    y = np.array(data["dnll2"], dtype=float)

    best = np.nan
    if "poi_mins" in arr.files:
        poi_mins = arr["poi_mins"]
        # poi_mins can be a structured array with field names
        try:
            best = float(poi_mins[poi_name])
        except Exception:
            # fallback: infer from minimum dnll2
            pass

    if not np.isfinite(best):
        # fallback: use minimum dnll2 point
        m = np.isfinite(x) & np.isfinite(y)
        if np.any(m):
            best = float(x[m][np.argmin(y[m])])
        else:
            best = np.nan

    return x, y, best


def load_theory(pred_pkl: str, unc_pkl: str) -> Tuple[np.ndarray, np.ndarray]:
    with open(pred_pkl, "rb") as f:
        pred = pickle.load(f)
    with open(unc_pkl, "rb") as f:
        unc = pickle.load(f)

    pred = np.array(pred, dtype=float)
    unc = np.array(unc, dtype=float)

    if pred.shape != (5, 3):
        raise ValueError(f"Expected theory pred shape (5,3), got {pred.shape} from {pred_pkl}")
    if unc.shape != (2, 5):
        raise ValueError(f"Expected theory unc shape (2,5), got {unc.shape} from {unc_pkl}")

    return pred, unc


def plot_njets_xs(
    merge_npz_by_poi: Dict[str, str],
    theory_pred_pkl: str,
    theory_unc_pkl: str,
    out_pdf: str,
    out_png: str,
    out_json: str,
    *,
    title: str = "HZZ",
    cms_label: str = "Preliminary",
    lumi_fb: Optional[float] = None,
) -> None:
    """
    Main entrypoint used by the Luigi/Law task.

    merge_npz_by_poi: dict { "r_Njets_0": "/path/to/merge.npz", ... }
    """
    _ensure_dir(out_pdf)
    _ensure_dir(out_png)
    _ensure_dir(out_json)

    pred, unc = load_theory(theory_pred_pkl, theory_unc_pkl)

    # binning: 5 steps for Njets=0..4 (you can relabel last as ">=4" if you want)
    bin_edges = np.arange(0, 6, 1, dtype=float)   # 0,1,2,3,4,5
    bin_centers = bin_edges[:-1] + 0.5

    # Extract r best-fit and 1-sigma
    pois_sorted = list(merge_npz_by_poi.keys())
    # keep stable order r_Njets_0..4 if present
    def _poi_key(p: str) -> int:
        try:
            return int(p.split("_")[-1])
        except Exception:
            return 999

    pois_sorted = sorted(pois_sorted, key=_poi_key)

    r_best = np.full(5, np.nan, dtype=float)
    r_lo = np.full(5, np.nan, dtype=float)
    r_hi = np.full(5, np.nan, dtype=float)

    intervals: Dict[str, Dict[str, float]] = {}

    for poi in pois_sorted:
        idx = _poi_key(poi)
        x, y, best = load_merge_npz(merge_npz_by_poi[poi], poi)
        iv = _find_interval_1sigma(x, y, best)

        if 0 <= idx < 5:
            r_best[idx] = iv.best
            r_lo[idx] = iv.lo
            r_hi[idx] = iv.hi

        intervals[poi] = {
            "best": float(iv.best) if np.isfinite(iv.best) else None,
            "lo_1sigma": float(iv.lo) if np.isfinite(iv.lo) else None,
            "hi_1sigma": float(iv.hi) if np.isfinite(iv.hi) else None,
        }

    # Central theory (baseline) and alternatives
    th_c = pred[:, 0]
    th_powheg = pred[:, 1]
    th_nonlops = pred[:, 2]

    # Convert to "measured cross section" using r * central theory
    data_xs = r_best * th_c
    data_err_up = (r_hi - r_best) * th_c
    data_err_dn = (r_best - r_lo) * th_c

    # Theory uncertainties (absolute) for central
    th_unc_up = unc[0, :]
    th_unc_dn = unc[1, :]

    # Prepare plot
    plt.style.use(hep.style.CMS)

    fig = plt.figure(figsize=(10, 8), dpi=120)
    ax1 = fig.add_axes((0.10, 0.35, 0.85, 0.60))
    ax2 = fig.add_axes((0.10, 0.08, 0.85, 0.22), sharex=ax1)

    # CMS label
    hep.cms.label(
        cms_label,
        data=True,
        lumi=(lumi_fb if lumi_fb is not None else None),
        com=13.6,
        ax=ax1,
        fontsize=18,
    )

    # --- Top: cross sections (steps + data points) ---
    # Data points (from likelihood)
    ax1.errorbar(
        bin_centers,
        data_xs,
        yerr=[data_err_dn, data_err_up],
        marker="o",
        linestyle="None",
        color="k",
        linewidth=2,
        ms=5,
        capsize=4,
        label="HZZ (stat $\oplus$ sys from likelihood)",
    )

    # Theory steps
    ax1.stairs(th_c, bin_edges, linewidth=2, label="Theory (baseline)", color="tab:blue")
    ax1.stairs(th_nonlops, bin_edges, linewidth=2, label="Theory (alt 1)", color="tab:purple")
    ax1.stairs(th_powheg, bin_edges, linewidth=2, label="Theory (alt 2)", color="brown")

    # Add hatched rectangles for theory uncertainty on baseline (simple per-bin band)
    # (kept intentionally simple to avoid over-styling)
    for c, v, u_dn, u_up in zip(bin_centers, th_c, th_unc_dn, th_unc_up):
        if not (np.isfinite(v) and np.isfinite(u_dn) and np.isfinite(u_up)):
            continue
        # small box around the center
        w = 0.35
        ax1.add_patch(
            plt.Rectangle(
                (c - w / 2.0, v - u_dn),
                w,
                u_dn + u_up,
                fill=False,
                lw=0,
                hatch="///",
                alpha=1.0,
            )
        )

    ax1.set_ylabel(r"$\sigma_{\mathrm{fid}}$ per Njets bin (arb. units)", fontsize=16)
    ax1.set_xlim(0, 5)
    ax1.set_ylim(bottom=0)
    ax1.tick_params(axis="both", labelsize=14)
    ax1.set_xticklabels([])

    # Legend
    ax1.legend(loc="upper right", fontsize=12, title=title, title_fontsize=12)

    # --- Bottom: ratio to baseline ---
    ratio_data = r_best
    ratio_err_up = (r_hi - r_best)
    ratio_err_dn = (r_best - r_lo)

    ax2.errorbar(
        bin_centers,
        ratio_data,
        yerr=[ratio_err_dn, ratio_err_up],
        marker="o",
        linestyle="None",
        color="k",
        linewidth=2,
        ms=5,
        capsize=4,
    )

    # baseline line at 1
    ax2.hlines(1.0, 0, 5, linewidth=1)

    # alternative theory ratios
    ax2.stairs(th_powheg / th_c, bin_edges, linewidth=2, color="brown")
    ax2.stairs(th_nonlops / th_c, bin_edges, linewidth=2, color="tab:purple")

    # baseline theory uncertainty band in ratio
    # draw as simple rectangles per bin
    for c, v, u_dn, u_up in zip(bin_centers, th_c, th_unc_dn, th_unc_up):
        if not (np.isfinite(v) and np.isfinite(u_dn) and np.isfinite(u_up) and v != 0):
            continue
        w = 0.35
        lo = 1.0 - (u_dn / v)
        hi = 1.0 + (u_up / v)
        ax2.add_patch(
            plt.Rectangle(
                (c - w / 2.0, lo),
                w,
                hi - lo,
                fill=False,
                lw=0,
                hatch="///",
                alpha=1.0,
            )
        )

    ax2.set_ylabel("Ratio to baseline", fontsize=14)
    ax2.set_xlabel(r"$N_{\mathrm{jets}}$", fontsize=16)

    ax2.set_xticks([0.5, 1.5, 2.5, 3.5, 4.5])
    ax2.set_xticklabels(["0", "1", "2", "3", r"$\geq 4$"], fontsize=14)
    ax2.tick_params(axis="y", labelsize=14)
    ax2.set_ylim(0.0, 3.0)

    # Save outputs
    fig.savefig(out_pdf, bbox_inches="tight", dpi=120)
    fig.savefig(out_png, bbox_inches="tight", dpi=120)
    plt.close(fig)

    # Save JSON summary
    payload = {
        "merge_npz_by_poi": merge_npz_by_poi,
        "theory_pred_pkl": theory_pred_pkl,
        "theory_unc_pkl": theory_unc_pkl,
        "bins": ["Njets=0", "Njets=1", "Njets=2", "Njets=3", "Njets>=4"],
        "r_intervals_1sigma": intervals,
        "theory_pred": {
            "baseline": th_c.tolist(),
            "alt1": th_nonlops.tolist(),
            "alt2": th_powheg.tolist(),
        },
        "theory_unc_abs": {
            "up": th_unc_up.tolist(),
            "down": th_unc_dn.tolist(),
        },
        "data_xs_from_r_times_baseline": {
            "xs": data_xs.tolist(),
            "err_up": data_err_up.tolist(),
            "err_down": data_err_dn.tolist(),
        },
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)