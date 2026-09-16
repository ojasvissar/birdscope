# Scientific methods and data contract

## 1. Sources and scope

The `ebirdst` example is a spatially restricted set of published Yellow-bellied Sapsucker estimates. Weekly Status 2023 and breeding Trends 2022 (2012–2022) are separate releases. The code verifies the installed `ebirdst` release against the configuration before loading them.

The `auk` zero-filling files are an independent Singapore sample from 2012. They pair observations for three kingfisher species with a sampling-event table. Zero-filling is valid only because the sampling-event denominator belongs to the same example scope as the observation extract. The software verifies that the target species occurs in the extract; it cannot prove arbitrary user-supplied EBD and sampling files have matching scope. This must be an explicit ingestion contract for future adapters.

Official references: [Status introduction](https://ebird.github.io/ebirdst/articles/status.html), [Trends methods and regional aggregation](https://ebird.github.io/ebirdst/articles/trends.html), and [auk](https://github.com/CornellLabofOrnithology/auk).

## 2. Raster support and area weighting

`terra::crop` restricts each source raster to the AOI’s projected bounding box before converting values to an array. This avoids materializing the entire global 52-layer raster. Native cells with finite estimates in at least one week are polygonized and clipped to Michigan. Cell ID refers to the cropped Status grid and is unique within this configured study; it is not a global persistent Cornell identifier.

For each cell-region intersection, store area in square kilometers in Equal Earth EPSG:8857. Region weights partition the supported Michigan cell footprints; a runtime check and integration test verify their sums and reconstruction of regional mean abundance. Region boundaries can split a cell, so the sum of per-region unique-cell counts can exceed the Michigan unique-cell count.

For each week:

```text
mean = Σ(area × finite estimate) / Σ(area with finite estimate)
support_fraction = area with finite abundance / area in the region's ever-supported footprint
```

Zeros are modeled values and must not be removed. Missing values are not converted to zero. `support_fraction` is relative to the ever-supported sample footprint, not all of Michigan, and says nothing about the number of contributing checklists. Occurrence summaries independently exclude missing occurrence values; the exported support area refers specifically to abundance.

Natural Earth is a generalized political boundary product, not a surveyed shoreline or habitat mask. Supported area is not terrestrial habitat area. Coarse model estimates are treated as uniform inside a cell. Shoreline intersections and fine regional boundaries introduce an approximation; report resolution and support when handing off a product.

No regional abundance confidence interval is claimed. The map inspector displays pointwise source lower and upper cell bounds. Averaging those bounds would not produce a defensible regional interval.

## 3. Environmental covariate preparation

WorldClim’s static, SRTM-derived elevation is supplied on a 10 arc-minute geographic grid. The pipeline crops it around Michigan and uses `terra::project(..., method="average")` to align it to the 27 km Status grid. Elevation units remain meters. Continuous covariates use averaging; categorical land cover would require a different operation, such as proportions or modal class.

The elevation value describes the original native cell footprint, while reported regional cell area is clipped to the political boundary. This distinction matters at boundary cells. Elevation is displayed as a separate exploratory layer and included in local covariate outputs. It is not included in the Singapore feature experiment, is not treated as contemporary land cover, and does not establish a causal relationship with abundance.

## 4. Regional trends and uncertainty

Trends use their own sinusoidal equal-area grid. `rasterize_trends` supplies its native resolution and CRS; cell-center coordinates and half-cell dimensions construct the source cell polygons. Those cells are transformed and intersected with the same AOIs. No Status-grid IDs or Status 2023 abundance values enter the trend weighting.

For region R and source ensemble replicate b:

```text
g_Rb = Σ_i (g_ib × n_ib × A_iR) / Σ_i (n_ib × A_iR)
```

Here `g_ib` is the source cell annual percentage trend, `n_ib` is its associated midpoint relative abundance, and `A_iR` is regional overlap area. Each regional replicate has its own weighted estimate. The final median, 10th and 90th percentiles are calculated across the 100 regional estimates.

Directions are descriptive interval labels: upper bound below zero = declining; lower bound above zero = increasing; otherwise uncertain. “Uncertain” does not establish stability. The method is a regional weighted mean of cell growth rates, not a refit of a regional population time series. Source replicate quantiles inherit the original modeling framework; do not interpret them as complete uncertainty about all conservation decisions.

The test suite contains a deliberately anticorrelated two-cell ensemble. Each regional replicate cancels to zero, so the interval must collapse to zero even though each cell has a broad marginal interval. This tests the reason for aggregating aligned replicates instead of marginal interval endpoints.

## 5. Checklist denominator and quality assessment

Configured defaults:

| Rule | Rationale |
|---|---|
| Unique, non-null sampling-event IDs | Avoid accidental duplicated survey rows |
| All species reported = 1 | Only complete lists support implicit non-detections |
| P21 stationary / P22 traveling | Comparable protocol families with usable effort |
| Duration 1–300 minutes | Limit extreme duration and require known effort |
| Distance 0–5 km | Limit extreme spatial coverage; stationary missing distance becomes zero |
| 1–10 observers | Remove extreme or unknown observer counts |
| Valid date, start time and coordinates | Prevent invalid temporal/spatial predictors |
| Shared group collapsed to one visit | Avoid counting the same joint survey repeatedly |

These are explicit demonstration thresholds, not immutable Cornell standards. Real projects should pre-register and assess their eligibility criteria with technical leads.

The pipeline keeps an attrition table of sequential exclusions, so each excluded row is counted once at the first failing stage. The specific sample has no additional shared-visit duplicates after eligibility filtering, but shared-list behavior is tested with a controlled fixture.

For shared groups, effort comes from a deterministic representative checklist (sorted event ID). Species detections are unioned across the group’s source members; counts take the maximum reported count rather than the sum. This assumes a shared group represents the same survey. A production pipeline should validate within-group time, location and effort agreement and use the provider’s reviewed shared-checklist conventions.

An approved numeric positive count or `X` is a detection. `X` does not become a numeric zero; its abundance count is unknown. Non-detected target species on otherwise eligible complete lists receive detection = 0 and count = 0. Rejected or malformed target observations without an accepted group detection yield an unknown target label, so that visit is excluded rather than falsely labeled a non-detection.

**Non-detection does not prove absence.** These models estimate conditional detection on this eligible sampling frame. Observer, site selection, weather, phenology and unmeasured effort can all influence the result.

## 6. Prespecified model-feature experiment

**Outcome:** target species detected on an eligible independent checklist.

**Candidates:**

1. Training-fold prevalence, without predictors.
2. L2-regularized logistic regression with log(1 + duration), log(1 + distance), number of observers, stationary-protocol indicator, and sine/cosine start-time harmonics.
3. The same model plus latitude, longitude, and sine/cosine day-of-year harmonics.

Each fit uses `C=1`, `solver="liblinear"`, at most 2,000 iterations, and the configured seed. Predictors are standardized using only training-fold statistics. There is no hyperparameter search. If a training fold contains only one outcome class, the fit explicitly falls back to that training prevalence and records the fallback. The supplied run needed no fallback.

**Spatial splits:** group visits by a 0.05° grid (roughly 5.6 km at Singapore’s latitude). Merge grid groups connected by the same locality ID using union-find. Apply five-fold GroupKFold, retaining all visits of each resulting group in one fold. Every candidate uses exactly the same folds. Runtime assertions reject group and locality overlap between train and test.

This protects against repeated localities crossing folds but does not create a geographic buffer. Nearby blocks may straddle a boundary, individual observers may cross folds, and there is no future-year holdout. Degrees are acceptable for this near-equatorial demonstration, not a global equal-distance blocking definition. These choices must be revisited for real study geography and the biological scale of interest.

**Scores:** Brier score and log loss assess probability quality; ROC AUC and average precision assess ranking. Calibration uses five fixed probability bins. Empty bins are omitted; one-observation bins are shown and must be interpreted cautiously. The calibration plot is descriptive and has no binomial uncertainty intervals.

**Comparison:** compute per-visit squared-error differences between candidate 3 and candidate 2. Resample complete spatial groups with replacement 500 times using the fixed seed. Each resample retains the paired predictions for the same visits. Report the 2.5th and 97.5th percentiles of the mean loss difference. The bootstrap holds trained out-of-fold predictions fixed; it does not refit models and does not capture all training-set variability. This is a screening experiment, not definitive independent validation.

The added-feature result did not establish improvement. Report this result rather than switching folds or searching models until a favorable result appears.

## 7. Output schema

### Weekly regional product

`region`, `week` (1–52), `date` (source prediction date), `abundance`, `occurrence`, `supported_area_km2`, `support_fraction`, `cells`.

There are 52 rows per region, including all-Michigan and the three bands. The weeks are the source product’s dates, not ISO week numbers. A season filter uses source-configured boundaries, including nonbreeding seasons that wrap across December/January.

### Regional trend product

`region`, `annual_percent`, `lower`, `upper`, `folds`, `direction`, `cells`.

Values are percent per year, not a proportion and not cumulative percentage change. The cell inspector separately exposes the source cumulative trend. The regional product uses an 80% interval, whereas the feature experiment’s paired loss interval is 95%; these intervals answer different questions.

### Provenance

Input SHA-256 checksums, scientific source hashes, dependency-lock hashes, seed, configuration, installed Python/R package versions, platform, timestamp and measured analysis time. No access keys or private observation fields are published. Raw input filenames may appear in the manifest to identify sources, but their contents are not embedded.

## 8. Remaining scientific validation

Before operational use: audit representativeness, missingness and effort across geography/time; confirm the full EBD and sampling-event scope; assess taxonomy and shared-checklist changes; compare generalized and reviewed boundaries; test masks and shoreline behavior; validate remote-sensing time alignment; evaluate blocks/buffers and temporal transfer; quantify uncertainty appropriate to the decision; validate against independent data where possible; and obtain scientific acceptance from product owners.
