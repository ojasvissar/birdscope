"""Local scientific compute -> versioned, compact, static scientific products."""
import argparse
import hashlib
import html
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import time
from datetime import datetime, timezone

import duckdb
import numpy as np
import pandas as pd

from .checklists import prepare_checklists
from .evaluation import evaluate
from .products import summarize_weekly, summarize_trends

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, data):
    def normalize(v):
        if isinstance(v, dict):
            return {str(k): normalize(x) for k, x in v.items()}
        if isinstance(v, (tuple, list, np.ndarray)):
            return [normalize(x) for x in v]
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (float, np.floating)):
            return round(float(v), 7) if np.isfinite(v) else None
        if isinstance(v, np.bool_):
            return bool(v)
        return v
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(normalize(data), allow_nan=False, separators=(",", ":")), encoding="utf8")
    tmp.replace(path)


def benchmark(weekly, cells):
    table = weekly.merge(cells[["cell_id", "area_km2"]], on="cell_id", validate="many_to_one")
    con = duckdb.connect()
    con.register("cell_weeks", table)
    con.execute("COPY cell_weeks TO 'outputs/cell_week.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.unregister("cell_weeks")
    times = {"pandas": [], "duckdb": []}
    expected = None
    for _ in range(5):
        start = time.perf_counter()
        # In-memory pandas versus warm local Parquet; intentionally different I/O paths.
        t = table.loc[table.abundance.notna()].copy()
        t["weighted"] = t.abundance*t.area_km2
        p = t.groupby("week")[["weighted", "area_km2"]].sum()
        expected = (p.weighted/p.area_km2).to_numpy()
        times["pandas"].append(time.perf_counter()-start)
        start = time.perf_counter()
        actual = con.execute("""SELECT week, SUM(abundance*area_km2)/SUM(area_km2) AS mean
          FROM read_parquet('outputs/cell_week.parquet') WHERE abundance IS NOT NULL
          GROUP BY week ORDER BY week""").df()["mean"].to_numpy()
        times["duckdb"].append(time.perf_counter()-start)
        np.testing.assert_allclose(actual, expected, rtol=1e-9, atol=1e-12)
    con.close()
    return {"rows": len(table), "repetitions": 5, "equivalent_results": True,
            "parquet_bytes": Path("outputs/cell_week.parquet").stat().st_size,
            "pandas_median_ms": float(np.median(times["pandas"])*1000),
            "duckdb_median_ms": float(np.median(times["duckdb"])*1000),
            "scope": "Small-sample aggregation only: in-memory pandas vs warm local Parquet. No large-scale performance claim."}


def make_report(data, trends, weekly):
    t = next(x for x in data["regional_trends"] if x["region"] == "all")
    series = [x for x in data["weekly_summary"] if x["region"] == "all"]
    peak = max(series, key=lambda x: x["abundance"] or 0)
    c = data["checklists"]
    rows = "".join(f'<tr><td>{html.escape(x["region"])}</td><td>{x["annual_percent"]:+.2f}%</td>'
                   f'<td>{x["lower"]:+.2f}% to {x["upper"]:+.2f}%</td><td>{x["direction"]}</td></tr>'
                   for x in data["regional_trends"])
    doc = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BirdScope · Michigan conservation brief</title><style>body{{font:17px/1.65 system-ui,sans-serif;color:#25302a;max-width:880px;margin:48px auto;padding:0 24px}}h1{{font-size:42px;line-height:1.1}}h2{{margin-top:40px}}.tag{{color:#296239;letter-spacing:.12em;font-size:13px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:12px;border-bottom:1px solid #ddd;text-align:left}}aside{{padding:18px;background:#edf5f2}}@media print{{body{{margin:0}}button{{display:none}}}}</style>
<p class="tag">© BirdScope / SCIENTIFIC BRIEF / OFFICIAL EBIRD SAMPLE</p>
<h1>Yellow-bellied Sapsucker<br>in Michigan</h1><p><i>Sphyrapicus varius</i> · Status 2023 · Breeding trends 2012–2022</p>
<button onclick="window.print()">Print / save PDF</button>
<h2>Question</h2><p>How does modeled relative abundance vary across the year, and how do estimated breeding trends differ between broad analytical regions?</p>
<h2>Results</h2><p>The area-weighted annual cycle peaks on {peak['date']} at {peak['abundance']:.3f} relative abundance units across the supported Michigan cells. This is a seasonal pattern in a single Status release, not a population trend.</p>
<p>The separate Trends release yields an abundance-and-area-weighted regional trend of <strong>{t['annual_percent']:+.2f}% per year</strong> (80% ensemble interval {t['lower']:+.2f}% to {t['upper']:+.2f}%). Its interval-based direction is <strong>{t['direction']}</strong>.</p>
<table><thead><tr><th>Region</th><th>Annual trend</th><th>80% interval</th><th>Direction</th></tr></thead><tbody>{rows}</tbody></table>
<p>Northern, central, and southern bands use 45.5°N and 44°N boundaries. These analytical areas are not ecological or administrative units.</p>
<h2>Interpretation for conservation</h2><p>Use these summaries to frame follow-up investigations and monitoring discussions. Resolve local habitat, detectability, sample support, management feasibility, and uncertainty before identifying an intervention. A coarse teaching subset cannot establish parcel-level priorities or causal habitat effects.</p>
<h2>Methods</h2><p>R ebirdst downloads the official sample. terra crops GeoTIFFs before reading cell arrays. sf intersects 27 km cells and regions in an equal-area CRS. Weekly summaries weight model values by intersection area and retain true zeros. Missing support is excluded and reported. WorldClim 2.1 SRTM-derived elevation is averaged onto the Status grid as a covariate preparation example.</p>
<p>Trends are processed on their own sinusoidal grid. For each of 100 source ensemble replicates, cell trends are weighted by relative abundance × area. The regional median, 10th percentile and 90th percentile are then calculated across replicates. Averaging cell confidence bounds would not provide regional uncertainty.</p>
<h2>Separate observational experiment</h2><p>The auk example contains {c['raw_sampling_events']} Singapore sampling events. Filtering leaves {c['eligible_visits']} independent eligible visits: {c['detections']} detections and {c['nondetections']} non-detections of Collared Kingfisher. Prevalence, effort-only logistic regression, and effort-plus-space-and-season logistic regression are compared with held-out spatial groups. This does not validate Cornell's Michigan model.</p>
<h2>Reproducibility</h2><p>Run {data['run']['id']}; seed {data['run']['seed']}. Input checksums, source fingerprints, versions and configuration are in the downloadable manifest. These regional summaries are independently derived from the official sample and are not official Cornell statewide statistics.</p>
<h2>Sources</h2><ul><li><a href="https://ebird.github.io/ebirdst/">Cornell Lab of Ornithology: ebirdst official sample and documentation</a></li><li>Status: Fink et al., data version 2023, released 2025. <a href="https://doi.org/10.2173/WZTW8903">DOI</a>.</li><li>Trends: Fink et al., data version 2022, released 2023. <a href="https://doi.org/10.2173/ebirdst.2022">DOI</a>.</li><li><a href="https://github.com/CornellLabofOrnithology/auk/tree/main/inst/extdata">auk teaching data</a> · <a href="https://www.worldclim.org/data/worldclim21.html">WorldClim elevation</a> · <a href="https://www.naturalearthdata.com/about/terms-of-use/">Natural Earth boundaries</a>.</li></ul></html>'''
    Path("dist/downloads/conservation-brief.html").write_text(doc, encoding="utf8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-spatial", action="store_true", help="Reuse R products only when their fingerprint matches")
    args = parser.parse_args()
    os.chdir(ROOT)
    start = time.perf_counter()
    cfg = json.loads(Path("config/analysis.json").read_text())
    for path in ["outputs", "outputs/private", "dist/data", "dist/downloads"]:
        Path(path).mkdir(parents=True, exist_ok=True)
    required = ["data/raw/2023/yebsap-example/config.json", "data/raw/zerofill-ex_ebd.txt",
                "data/raw/zerofill-ex_sampling.txt", "data/raw/wc2.1_10m_elev.zip", "data/raw/states.geojson"]
    if not all(Path(p).exists() for p in required):
        raise SystemExit("Missing data. Run Rscript scripts/fetch_data.R first.")
    raw = {str(p): digest(p) for p in sorted(Path("data/raw").rglob("*"))
           if p.is_file() and p.name != "R-session.txt" and "elevation" not in p.parts}
    lock = Path("data/manifest.lock.json")
    if lock.exists():
        expected = json.loads(lock.read_text())
        changed = [p for p, h in expected.items() if raw.get(p) != h]
        if changed:
            raise SystemExit("Input checksum mismatch. Review changes before refreshing data/manifest.lock.json: " + ", ".join(changed))
    else:
        write_json(lock, raw)
    fingerprint = hashlib.sha256((json.dumps(raw, sort_keys=True)+digest("scripts/spatial.R")+
                                  digest("config/analysis.json")).encode()).hexdigest()
    cache = Path("outputs/spatial/fingerprint.txt")
    if args.skip_spatial:
        if not cache.exists() or cache.read_text() != fingerprint:
            raise SystemExit("Spatial cache missing or stale. Run without --skip-spatial.")
    else:
        subprocess.run(["Rscript", "scripts/spatial.R"], check=True)
        cache.write_text(fingerprint)
    print("Summarizing weekly raster products and trend ensembles…", flush=True)
    spatial = Path("outputs/spatial")
    weekly = pd.read_csv(spatial/"weekly.csv")
    cells = pd.read_csv(spatial/"cells.csv")
    weights = pd.read_csv(spatial/"weights.csv")
    if weekly.duplicated(["cell_id", "week"]).any():
        raise ValueError("Duplicate cell-week")
    if not np.allclose(weights.groupby("cell_id").area_km2.sum().sort_index(),
                       cells.set_index("cell_id").area_km2.sort_index(), rtol=1e-6):
        raise ValueError("Region areas do not partition status support")
    summaries = summarize_weekly(weekly, cells, weights)
    folds = pd.read_csv(spatial/"trend_folds.csv")
    tw = pd.read_csv(spatial/"trend_weights.csv")
    trends, regional_folds = summarize_trends(folds, tw)
    if not (trends.folds == 100).all():
        raise ValueError("Expected 100 complete trend ensemble replicates per region")
    print("Preparing checklist denominator and spatial feature experiment…", flush=True)
    obs = pd.read_csv("data/raw/zerofill-ex_ebd.txt", sep="\t", low_memory=False)
    sed = pd.read_csv("data/raw/zerofill-ex_sampling.txt", sep="\t", low_memory=False)
    frame, checklist_summary = prepare_checklists(obs, sed, cfg)
    experiment_result = evaluate(frame, cfg)
    if isinstance(experiment_result, tuple):
        experiment, oof = experiment_result
        oof.to_csv("outputs/private/oof_predictions.csv", index=False)
    else:
        experiment = experiment_result
    frame.to_csv("outputs/private/eligible_checklists.csv", index=False)
    bench = benchmark(weekly, cells)
    metadata = json.loads((spatial/"metadata.json").read_text())
    source = {str(p): digest(p) for folder in ["src", "scripts", "config"] for p in sorted(Path(folder).rglob("*"))
              if p.is_file() and p.suffix in [".py", ".R", ".json", ".sh"]}
    source.update({p: digest(p) for p in ["requirements.txt", "renv.lock"] if Path(p).exists()})
    run_id = hashlib.sha256(json.dumps({"inputs": raw, "source": source}, sort_keys=True).encode()).hexdigest()[:12]
    run = {"id": run_id, "created_at": datetime.now(timezone.utc).isoformat(), "seed": cfg["seed"],
           "python": platform.python_version(), "platform": platform.platform(), "config": cfg,
           "packages": {p: importlib.metadata.version(p) for p in ["numpy", "pandas", "duckdb", "scikit-learn", "scipy"]},
           "input_sha256": raw, "source_sha256": source, "spatial": metadata,
           "elapsed_seconds": round(time.perf_counter()-start, 3)}
    data = {"schema_version": 1, "run": {k:run[k] for k in ["id", "created_at", "seed", "elapsed_seconds"]},
            "metadata": metadata, "regions": cfg["regions"], "weekly_summary": summaries.to_dict("records"),
            "regional_trends": trends.to_dict("records"), "checklists": checklist_summary,
            "experiment": experiment, "benchmark": bench}
    # Web map objects contain transformed derived products, no observational microdata.
    status_geo = json.loads((spatial/"status_cells.geojson").read_text())
    for feature in status_geo["features"]:
        p = feature["properties"]; cell_id = p["cell_id"]
        records = weekly.loc[weekly.cell_id.eq(cell_id)].sort_values("week")
        p["abundance"] = records.abundance.to_list()
        p["lower"] = records.lower.to_list(); p["upper"] = records.upper.to_list()
        p["occurrence"] = records.occurrence.to_list()
        p["regions"] = weights.loc[weights.cell_id.eq(cell_id), "region"].to_list()
    trend_geo = json.loads((spatial/"trend_cells.geojson").read_text())
    for feature in trend_geo["features"]:
        p = feature["properties"]
        p["regions"] = tw.loc[tw.srd_id.eq(p["srd_id"]), "region"].to_list()
    write_json("dist/data/status.geojson", status_geo)
    write_json("dist/data/trends.geojson", trend_geo)
    write_json("dist/data/analysis.json", data)
    write_json("dist/downloads/provenance.json", run)
    write_json("dist/downloads/model-evaluation.json", experiment)
    summaries.to_csv("dist/downloads/weekly-regions.csv", index=False, float_format="%.7f")
    trends.to_csv("dist/downloads/regional-trends.csv", index=False, float_format="%.7f")
    regional_folds.to_csv("outputs/regional-trend-folds.csv", index=False)
    make_report(data, trends, summaries)
    subprocess.run(["Rscript", "scripts/figures.R"], check=True)
    write_json("outputs/run.json", run)
    print(f"Complete. Run {run_id}: {len(cells)} status cells, {len(weekly):,} cell-weeks, "
          f"{len(frame)} eligible checklists. Outputs in dist/ and outputs/.")


if __name__ == "__main__":
    main()
