"""Area-weighted status summaries and ensemble-aware trend summaries."""
import numpy as np
import pandas as pd


def weighted_mean(values, weights):
    x, w = np.asarray(values, float), np.asarray(weights, float)
    if np.any(np.isfinite(w) & (w < 0)):
        raise ValueError("Area or abundance weights cannot be negative")
    keep = np.isfinite(x) & np.isfinite(w) & (w > 0)
    return float(np.average(x[keep], weights=w[keep])) if keep.any() else None


def summarize_weekly(weekly, cells, weights):
    # One denominator per region/week, excluding missing model support, retaining zeros.
    joined = weekly.merge(weights, on="cell_id", validate="many_to_many")
    all_rows = weekly.merge(cells[["cell_id", "area_km2"]], on="cell_id", validate="many_to_one")
    all_rows["region"] = "all"
    joined = pd.concat([joined, all_rows], ignore_index=True)
    rows = []
    for (region, week), d in joined.groupby(["region", "week"], sort=True):
        keep = d["abundance"].notna()
        area = float(d.loc[keep, "area_km2"].sum())
        rows.append({"region": region, "week": int(week), "date": d["date"].iloc[0],
                     "abundance": weighted_mean(d["abundance"], d["area_km2"]),
                     "occurrence": weighted_mean(d["occurrence"], d["area_km2"]),
                     "supported_area_km2": area,
                     "support_fraction": area / float(d["area_km2"].sum()),
                     "cells": int(d.loc[keep, "cell_id"].nunique())})
    return pd.DataFrame(rows)


def summarize_trends(folds, weights):
    if folds.duplicated(["srd_id", "fold"]).any():
        raise ValueError("Duplicate cell-fold in trends")
    joined = folds.merge(weights, on="srd_id", validate="many_to_many")
    all_weights = weights.groupby("srd_id", as_index=False)["area_km2"].sum()
    all_rows = folds.merge(all_weights, on="srd_id", validate="many_to_one")
    all_rows["region"] = "all"
    joined = pd.concat([joined, all_rows], ignore_index=True)
    estimates = []
    for (region, fold), d in joined.groupby(["region", "fold"]):
        estimates.append({"region": region, "fold": int(fold),
                          "annual_percent": weighted_mean(d["abd_ppy"], d["abd"]*d["area_km2"])})
    estimates = pd.DataFrame(estimates)
    results = []
    for region, d in estimates.groupby("region"):
        v = d["annual_percent"].dropna().to_numpy()
        if not len(v):
            continue
        lo, med, hi = np.quantile(v, [.1, .5, .9])
        results.append({"region": region, "annual_percent": float(med), "lower": float(lo),
                        "upper": float(hi), "folds": len(v),
                        "direction": "declining" if hi < 0 else "increasing" if lo > 0 else "uncertain",
                        "cells": int(weights.loc[weights.region.eq(region), "srd_id"].nunique())
                        if region != "all" else int(weights.srd_id.nunique())})
    return pd.DataFrame(results), estimates
