"""Pre-specified feature experiment with honest out-of-block predictions."""
import time
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score, average_precision_score, log_loss

EFFORT = ["log_duration", "log_distance", "observers", "stationary", "hour_sin", "hour_cos"]
FEATURES = {"prevalence": [], "effort": EFFORT,
            "space_time": EFFORT + ["latitude", "longitude", "doy_sin", "doy_cos"]}
NAMES = {"prevalence": "Training prevalence", "effort": "Effort only",
         "space_time": "Effort + space + season"}


def evaluate(frame, config):
    n_groups = frame["block"].nunique()
    if n_groups < 3 or len(frame) < 30 or frame["detected"].nunique() < 2:
        return {"status": "insufficient_data", "reason": "Need ≥30 visits, ≥3 blocks, and both labels"}
    y = frame["detected"].to_numpy()
    groups = frame["block"].to_numpy()
    splits = list(GroupKFold(n_splits=min(config["cv_folds"], n_groups)).split(frame, y, groups))
    fold_id = np.zeros(len(frame), dtype=int)
    split_rows = []
    predictions = {}
    models = []
    for i, (train, test) in enumerate(splits):
        assert not set(groups[train]) & set(groups[test]), "Spatial leakage"
        assert not set(frame.iloc[train]["LOCALITY ID"].dropna()) & set(frame.iloc[test]["LOCALITY ID"].dropna()), "Locality leakage"
        fold_id[test] = i + 1
        split_rows.append({"fold": i+1, "train_n": len(train), "test_n": len(test),
                           "test_detections": int(y[test].sum()), "test_blocks": len(set(groups[test]))})
    for key, cols in FEATURES.items():
        start = time.perf_counter()
        pred = np.full(len(frame), np.nan)
        fallback = 0
        for train, test in splits:
            if not cols or len(np.unique(y[train])) < 2:
                pred[test] = y[train].mean()
                fallback += int(bool(cols))
            else:
                model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, solver="liblinear", max_iter=2000,
                                      random_state=config["seed"]))
                model.fit(frame.iloc[train][cols], y[train])
                pred[test] = model.predict_proba(frame.iloc[test][cols])[:, 1]
        assert np.isfinite(pred).all()
        predictions[key] = pred
        calibration = []
        bins = np.minimum((pred*5).astype(int), 4)
        for b in range(5):
            mask = bins == b
            if mask.any():
                calibration.append({"predicted": float(pred[mask].mean()),
                                    "observed": float(y[mask].mean()), "n": int(mask.sum())})
        models.append({"id": key, "name": NAMES[key], "features": cols,
                       "brier": float(brier_score_loss(y, pred)),
                       "roc_auc": float(roc_auc_score(y, pred)),
                       "average_precision": float(average_precision_score(y, pred)),
                       "log_loss": float(log_loss(y, np.clip(pred, 1e-8, 1-1e-8))),
                       "elapsed_seconds": round(time.perf_counter()-start, 4),
                       "constant_training_fallback_folds": fallback, "calibration": calibration})
    # Paired block bootstrap of loss differences; holds fitted OOF models fixed.
    rng = np.random.default_rng(config["seed"])
    unique = np.unique(groups)
    delta = (y-predictions["space_time"])**2 - (y-predictions["effort"])**2
    boot = []
    for _ in range(config["bootstrap_replicates"]):
        ix = np.concatenate([np.flatnonzero(groups == g) for g in rng.choice(unique, len(unique), replace=True)])
        boot.append(float(delta[ix].mean()))
    result = {"status": "complete", "design": "5-fold spatial GroupKFold; 0.05° blocks merged by locality",
              "folds": split_rows, "models": models, "n": len(frame), "blocks": len(unique),
              "comparison": {"delta_brier": float(delta.mean()),
                 "lower": float(np.quantile(boot, .025)), "upper": float(np.quantile(boot, .975)),
                 "replicates": len(boot), "interval": "95% paired spatial-block bootstrap; fixed OOF predictions"}}
    oof = frame[["visit_id", "block", "detected"]].copy()
    oof["fold"] = fold_id
    for key, pred in predictions.items():
        oof[key] = pred
    return result, oof
