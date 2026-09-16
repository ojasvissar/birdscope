# Architecture decisions

## ADR 1 — Use a real, bounded case study

**Decision:** use the official 27 km Yellow-bellied Sapsucker Michigan sample, paired with a separately labeled `auk` checklist example.

**Reason:** it can be reproduced without private account access and is directly relevant to the team’s tools. It includes weekly rasters, source ensemble trends, configuration and standard GIS formats. A tiny reproducible real case is defensible; invented maps would not demonstrate scientific data handling.

**Tradeoff:** neither sample represents the distribution or scale of a full production project. Inferences are limited to sample support, and the observational experiment cannot validate the published Michigan model. We do not infer unsupported multi-species or multi-year coverage.

## ADR 2 — R for spatial access; Python for evaluation

**Decision:** retain Cornell’s `ebirdst` R interface for data acquisition and product loading; use `terra` and `sf` for spatial computation; use Python/pandas/scikit-learn for experiment and reporting logic.

**Reason:** this follows provider-supported data access and uses each language where its ecosystem is strongest. The boundary between languages is documented CSV/GeoJSON/GeoTIFF/Parquet, rather than a fragile embedded interpreter bridge.

**Tradeoff:** two runtime environments need version control and installation. The R lock and Python pins record the working environment. We avoid changing system libraries; a new-machine setup restores to `.R-library` and `.venv`.

**Alternative:** an all-R `targets` workflow would be an excellent fit in an R-first team, and an all-Python stack could use the documented download API plus rasterio/geopandas. There is no claim that mixed-language orchestration is inherently faster.

## ADR 3 — Model the estimand before designing the chart

**Decision:** keep seasonal status, long-term trends, observed detection frequency and prediction quality separate in the UI and products.

**Reason:** these numbers answer different questions. Relative abundance is a standardized expected checklist count; it is not population size. A within-year peak is not a growth rate. A detection model on Singapore records is not an estimate of Michigan abundance.

**Consequence:** regional trend summaries use the Trends grid and ensemble; the seasonal explorer uses the Status grid. A user cannot accidentally apply a weekly filter to a long-term trend estimate.

## ADR 4 — Equal-area intersections, not point-in-region shortcuts

**Decision:** build cell polygons in each source’s native grid, transform to EPSG:8857 and intersect them with the AOI and its analytical bands. Use the resulting intersection areas as weights.

**Reason:** cells on region boundaries should contribute in proportion to their regional overlap. Longitude/latitude areas are unsuitable for this weighting. Status is Equal Earth and Trends is sinusoidal; row index is never used to join the two products.

**Tradeoff:** explicit polygon intersection is convenient for hundreds of cells but expensive for continental millions. A large deployment should use tiled zonal extraction or an exact-extraction engine with cached geometries and equivalent tests. Native raster values remain constant within each coarse cell, including across coastlines. This is not fine-resolution habitat mapping.

## ADR 5 — Carry source ensembles through regional aggregation

**Decision:** compute one regional trend per source replicate, then calculate quantiles across those regional estimates.

**Reason:** averaging cell confidence limits does not produce a confidence interval for the regional statistic. Keeping aligned source replicates retains their joint spatial structure for the summary supported by the source product.

**Tradeoff:** the interval inherits the source ensemble’s modeling assumptions and does not represent every possible sampling or ecological uncertainty. A 10th–90th percentile interval is an 80% source ensemble interval, not a claim of 95% certainty.

## ADR 6 — Small prespecified experiments, not a model leaderboard

**Decision:** compare a prevalence baseline, effort-only logistic regression, and the same effort model augmented by spatial coordinates and annual harmonics. Use fixed regularization and identical folds.

**Reason:** a small sample favors an interpretable feature experiment. Splitting observations randomly would allow nearby visits or the same locality to enter both train and test. No model selection is performed on the held-out results.

**Tradeoff:** unbuffered 0.05° blocks only partially address spatial dependence; observer leakage and temporal transfer remain. Logistic regression is not Cornell’s production model. A later experiment should use larger regional holdouts, temporal tests and independently reviewed feature definitions.

`liblinear` was selected for the small regularized fit; the initial local default solver produced numerical runtime warnings in this environment. The final executed solver completed without those warnings. All held-out predictions are checked for finiteness and the valid probability range.

## ADR 7 — Static delivery over a precomputed product bundle

**Decision:** authored HTML/CSS/ES modules, local GeoJSON and SVG charts. No frontend build pipeline or runtime API server.

**Reason:** scientific compute does not need to run on a page view. The entire delivered site is small and can run offline through any static HTTP server. No browser requests depend on public tiles, fonts or map keys. Computation can later run on a cluster while product serving remains simple.

**Tradeoff:** the application is a fixed study with precomputed results. It has no arbitrary geometry uploads, live data refresh, job queue, authentication implementation, editing database or general query API. A static host’s access policy is separate from the app’s code. User-selected exports filter existing products, not newly executed scientific jobs.

The map is a simple local display projection. Area, alignment and uncertainty are computed upstream, not inferred from screen pixels. SVG is suitable for this sample; vector tiles or raster tiles would be needed for much larger maps.

## ADR 8 — Provenance as a product

**Decision:** compute SHA-256 checksums for every raw file and scientific source file; record configuration, software versions and a deterministic run ID derived from inputs and source. Preserve original inputs locally. Downloads include lineage.

**Reason:** a reviewer should be able to identify which source release and code produced a number. A UI screenshot alone is not a scientific artifact.

**Tradeoff:** input hashes detect upstream mutation but do not archive the upstream server. For long-term reproducibility, retain authorized immutable source snapshots in institutional storage. Exact floating-point reproducibility across different operating systems or BLAS/GDAL builds is not promised; contracts use scientifically appropriate numerical tolerances.

Elapsed time and creation timestamp are operational metadata; they change between runs. Run ID is a scientific source/input fingerprint, not a hash of output bytes or a substitute for a Git commit. The manifest records the actual runtime package versions.

## ADR 9 — File-backed analytical demonstration without overclaiming scale

**Decision:** export a Zstandard-compressed Parquet table and compare an area-weighted pandas aggregation with a DuckDB Parquet query.

**Reason:** this illustrates a practical route from exploratory analysis toward reusable tabular products and file-backed queries. Numerical equivalence is asserted before reporting performance.

**Tradeoff:** at 15,236 rows, overhead dominates. pandas is measured in memory and DuckDB reads a warm local file. These are different I/O paths; the reported milliseconds are not a fair engine speed ranking and cannot establish performance on billions of records.

Production benchmarking needs representative partitions, controlled cold/warm cache runs, I/O volume, peak memory, wall time, concurrency, scheduler accounting and cost. Larger data should be filtered and projected into needed columns before materialization.

## Failure behavior and maintainability

- Missing or mutated inputs fail with explicit instructions; the pipeline does not fabricate replacements.
- Duplicate checklist identifiers, duplicate trend replicate rows, invalid probabilities, inconsistent raster geometry, and failed area partition checks fail computation.
- Stale R intermediates cannot be reused with `--skip-spatial`; their fingerprint must match inputs, config and the R script.
- Individual JSON files are replaced atomically. The complete multi-file output bundle is not atomic; a production publisher must write to a run-specific staging directory and swap a manifest pointer only after validation.
- A failed local pipeline does not publish anything. Deployment is a distinct step after successful checks.
- There is no shared mutable database. Multiple simultaneous writers to this checkout are unsupported.
- The browser has an explicit data-loading error and retry state. Data selectors expose fixed valid options; external source strings are escaped before HTML insertion.
- Raw checklist files and private OOF predictions are ignored by Git and are not placed in `dist/`. Full-data access keys must remain environment-managed, never in URLs saved to manifests or frontend assets.

## HPC handoff

`hpc/analysis.slurm` is a single-job submission template. It requests resources and caps native thread counts. It has not been executed on a cluster. It deliberately avoids an array writing concurrently to shared output files.

Before scaling to many species, make species/AOI/release part of the task identity, use a unique scratch and output directory per task, cache immutable inputs, and publish an index only after successful validation. Use scheduler-level retries for transient acquisition errors, not silent retries for scientific integrity failures. Include product owners, retention, licensing and scientific approval in the operational design.
