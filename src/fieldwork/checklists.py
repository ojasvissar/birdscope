"""Build an eligible checklist denominator before creating non-detections.

No observer IDs, locality names, exact coordinates or checklist IDs are published.
Group members represent one visit: counts use max, detections use logical any.
"""
import numpy as np
import pandas as pd

ID = "SAMPLING EVENT IDENTIFIER"


def prepare_checklists(observations, sampling, config):
    required = [ID, "GROUP IDENTIFIER", "ALL SPECIES REPORTED", "PROTOCOL CODE",
                "DURATION MINUTES", "EFFORT DISTANCE KM", "NUMBER OBSERVERS",
                "LATITUDE", "LONGITUDE", "OBSERVATION DATE", "TIME OBSERVATIONS STARTED", "LOCALITY ID"]
    missing = set(required) - set(sampling.columns)
    if missing:
        raise ValueError(f"Sampling data missing columns: {sorted(missing)}")
    if sampling[ID].duplicated().any() or sampling[ID].isna().any():
        raise ValueError("Sampling event identifiers must be non-null and unique")
    if config["target_species"] not in set(observations["COMMON NAME"]):
        raise ValueError("Target species is absent from this observation extract; verify its scope")
    s = sampling.copy()
    s["visit_id"] = np.where(s["GROUP IDENTIFIER"].notna(),
                              "group:" + s["GROUP IDENTIFIER"].fillna("").astype(str),
                              "list:" + s[ID].astype(str))
    all_visits = s[[ID, "visit_id"]]
    stages = [{"stage": "Sampling events", "remaining": len(s), "removed": 0}]

    def retain(label, mask):
        nonlocal s
        before = len(s)
        s = s.loc[mask].copy()
        stages.append({"stage": label, "remaining": len(s), "removed": before - len(s)})

    retain("Complete checklists", s["ALL SPECIES REPORTED"].eq(1))
    retain("Stationary / traveling", s["PROTOCOL CODE"].isin(["P21", "P22"]))
    s["duration"] = pd.to_numeric(s["DURATION MINUTES"], errors="coerce")
    s["distance"] = pd.to_numeric(s["EFFORT DISTANCE KM"], errors="coerce")
    # Stationary protocols have distance zero even when the export leaves it blank.
    s.loc[s["PROTOCOL CODE"].eq("P21") & s["distance"].isna(), "distance"] = 0
    s["observers"] = pd.to_numeric(s["NUMBER OBSERVERS"], errors="coerce")
    retain("Effort limits", s["duration"].between(1, config["max_duration_minutes"]) &
           s["distance"].between(0, config["max_distance_km"]) &
           s["observers"].between(1, config["max_observers"]))
    s["latitude"] = pd.to_numeric(s["LATITUDE"], errors="coerce")
    s["longitude"] = pd.to_numeric(s["LONGITUDE"], errors="coerce")
    s["date"] = pd.to_datetime(s["OBSERVATION DATE"], errors="coerce")
    times = pd.to_timedelta(s["TIME OBSERVATIONS STARTED"].astype(str), errors="coerce")
    s["hour"] = times.dt.total_seconds() / 3600
    retain("Valid location, date & time", s["latitude"].between(-90, 90) &
           s["longitude"].between(-180, 180) & s["date"].notna() & s["hour"].between(0, 24, inclusive="left"))
    # Deterministic representative for effort, union of species detections across group.
    before = len(s)
    s = s.sort_values(ID).drop_duplicates("visit_id").copy()
    stages.append({"stage": "Independent shared visits", "remaining": len(s), "removed": before-len(s)})
    target = observations.loc[observations["COMMON NAME"].eq(config["target_species"])].copy()
    target = target.merge(all_visits, on=ID, how="inner", validate="many_to_one")
    approved = target["APPROVED"].eq(1)
    count = pd.to_numeric(target["OBSERVATION COUNT"], errors="coerce")
    present = approved & (count.gt(0) | target["OBSERVATION COUNT"].astype(str).str.upper().eq("X"))
    detected_visits = set(target.loc[present, "visit_id"])
    unknown = set(target.loc[~approved | (~present & count.isna()), "visit_id"]) - detected_visits
    retain("Known observation labels", ~s["visit_id"].isin(unknown))
    s["detected"] = s["visit_id"].isin(detected_visits).astype(int)
    counts = target.loc[present].assign(n=count[present]).groupby("visit_id")["n"].max()
    s["count"] = s["visit_id"].map(counts)
    s.loc[s["detected"].eq(0), "count"] = 0
    s["stationary"] = s["PROTOCOL CODE"].eq("P21").astype(int)
    s["doy_sin"] = np.sin(2*np.pi*s["date"].dt.dayofyear/365.25)
    s["doy_cos"] = np.cos(2*np.pi*s["date"].dt.dayofyear/365.25)
    s["hour_sin"] = np.sin(2*np.pi*s["hour"]/24)
    s["hour_cos"] = np.cos(2*np.pi*s["hour"]/24)
    s["log_duration"] = np.log1p(s["duration"])
    s["log_distance"] = np.log1p(s["distance"])
    size = config["spatial_block_degrees"]
    s["block"] = (np.floor(s["longitude"]/size).astype(int).astype(str) + ":" +
                   np.floor(s["latitude"]/size).astype(int).astype(str))
    # Merge blocks connected by repeated locality IDs to avoid localities crossing folds.
    parent = {v: v for v in s["block"].unique()}
    def root(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v
    for _, rows in s.groupby("LOCALITY ID"):
        blocks = sorted(rows["block"].unique())
        for b in blocks[1:]:
            parent[root(b)] = root(blocks[0])
    s["block"] = s["block"].map(root)
    summary = {"species": config["target_species"], "region": "Singapore", "year": 2012,
               "raw_observations": len(observations), "raw_sampling_events": len(sampling),
               "eligible_visits": len(s), "detections": int(s["detected"].sum()),
               "nondetections": int((1-s["detected"]).sum()), "spatial_blocks": s["block"].nunique(),
               "prevalence": float(s["detected"].mean()) if len(s) else None,
               "stages": stages, "presence_only_counts": int(s["count"].isna().sum())}
    return s.reset_index(drop=True), summary
