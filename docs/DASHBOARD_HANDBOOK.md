# BirdScope dashboard handbook

A complete walkthrough of what the dashboard shows, what every number means, how each
number is computed, and how far each one can honestly be pushed.

This is the interpretive companion to the other documents. It does not restate them:

| Document | Answers |
|---|---|
| `docs/METHODS.md` | The formal scientific contract and formulas |
| `docs/ARCHITECTURE.md` | Why the system is built this way (ADRs) |
| `docs/REVIEW.md` | Acceptance checklist and manual verification steps |
| **This file** | What you are looking at on screen, and how to read it |

All figures quoted here come from run **`ed1cad1e208f`** (seed `20260916`), the run whose
manifest ships in `dist/downloads/provenance.json`. If you re-run the pipeline against the
same pinned inputs, the run ID and every number below should reproduce exactly.

---

## 0. The thirty-second orientation

BirdScope is a static, precomputed dashboard over **two separate studies** that happen to
live in one interface. Almost every misreading of this dashboard comes from blurring them.

```
STUDY A — Michigan                         STUDY B — Singapore
Yellow-bellied Sapsucker                   Collared Kingfisher
(Sphyrapicus varius)                       2012 checklists

Cornell's published model output           Raw observations + sampling events
  · Status  2023  · 52 weeks               · 729 sampling events
  · Trends  2022  · 2012–2022              · 204 eligible visits after filtering
  · 27 km grids                            · Our own models, fit here

Views 01, 02, 04                           View 03
"What does the published product say       "Can we build and honestly evaluate
 about Michigan?"                           a detection model from raw checklists?"
```

Study A **consumes** models Cornell already fit. We do spatial aggregation and uncertainty
propagation on top of them. Study B is the only place where **we** fit a model, and it is
deliberately a different species, continent, and data type — so that no reader can mistake
our small logistic regression for a validation of Cornell's Michigan estimates.

The sidebar reflects this: the "CURRENT VIEW" block flips from *Michigan, USA · Status 2023
· Trends 2022* to *Singapore · 2012 · Collared Kingfisher* when you enter the Experiment lab.

---

## 1. Vocabulary: every term that appears on screen

Read this section once and the rest of the dashboard decodes itself.

### 1.1 Relative abundance

**On screen:** the headline metric in view 01, the map's default layer, the y-axis of the
annual cycle chart.

**Definition:** the expected count of the species on a **standardized checklist** — a 2 km,
1 hour traveling checklist, started at the optimal time of day for detection, by an observer
of typical skill, on that week, in that 27 km cell.

**What it is not:**

- not a population size or a count of birds
- not a density in birds/km²
- not the number of birds anyone actually saw

It is an *expected observation under fixed effort*. That fixed-effort standardization is the
whole point: it lets you compare cell to cell and week to week without effort differences
contaminating the comparison. The units are therefore "birds per standardized checklist",
which the UI abbreviates to "relative abundance units".

**Why a Michigan mean of 0.649 at peak is not alarming:** a value below 1 simply means the
average standardized checklist in the supported area is expected to turn up less than one
sapsucker. For a woodpecker at 27 km resolution this is ordinary.

### 1.2 Occurrence / encounter probability

The modeled probability that a standardized checklist **detects the species at least once**,
bounded in [0, 1]. Abundance and occurrence answer different questions: occurrence is about
*whether* you see it, abundance about *how many*. A cell can have high occurrence and low
abundance (reliably present, always singletons).

In Michigan at week 25 the area-weighted occurrence is 0.169 against an abundance of 0.239 —
roughly "a 17% chance of encountering the species per standardized checklist".

### 1.3 Detection vs. non-detection vs. absence

Used in view 03 only.

- **Detection** — the species was reported on a complete checklist.
- **Non-detection** — the observer reported *all species seen*, and this species was not
  among them. This is a real, informative zero.
- **Absence** — the species was not there. **The dashboard never claims this.** A
  non-detection is a joint statement about the bird and the observer; a quiet bird, a bad
  hour, or a novice observer all produce non-detections at occupied sites.

This is why the pipeline only builds zeros from **complete checklists** (`ALL SPECIES
REPORTED = 1`). An incomplete checklist that omits the species tells you nothing.

### 1.4 The eligible visit (the denominator)

A "visit" is one independent observation event. It is not the same as a checklist row,
because eBird **shared checklists** duplicate a single outing across every participant. The
pipeline collapses each share group to one visit (`group:<GROUP IDENTIFIER>`, falling back to
`list:<SAMPLING EVENT IDENTIFIER>` for unshared lists) so that a popular group outing does
not enter the model five times and inflate apparent sample size.

Within a group, effort fields come from one deterministic representative (sorted by sampling
event ID) while the detection label is the **logical OR** across the group — if anyone in the
party saw it, the visit is a detection.

### 1.5 Spatial block

A 0.05° cell of latitude/longitude used as the grouping unit for cross-validation, with a
union-find merge step: any two blocks that share a `LOCALITY ID` are merged into one block.
Without that merge, a single popular birding hotspot straddling a block boundary would appear
in both training and test folds, and the model would be scored partly on sites it had
memorized. The run has 204 visits distributed across 23 merged blocks.

### 1.6 Support / supported area / support fraction

Cornell's model does not produce estimates everywhere. A cell is **supported** in a week when
the model emitted a finite value there.

- **Supported area** — the summed km² of cells with a finite abundance estimate that week.
- **Support fraction** — supported area ÷ the region's *ever-supported* footprint.

The denominator matters: support fraction is **not** "fraction of Michigan covered". It is
"fraction of the area this product ever covers that is covered this week". Michigan's support
fraction ranges from 0.996 to 1.000 across the year — the sample is essentially complete, so
the weekly means are not being driven by a shifting footprint. In a larger study this number
is the first thing to check before believing a seasonal curve.

### 1.7 Analytical region / band

Three latitude bands clipped to Michigan, defined in `config/analysis.json`:

| Band | Latitude | Status cells | Supported area |
|---|---|---|---|
| Northern | 45.5°N – 49°N | 110 | 69,228 km² |
| Central | 44°N – 45.5°N | 79 | 46,399 km² |
| Southern | 41°N – 44°N | 129 | 82,205 km² |
| All Michigan | — | 293 | 197,832 km² |

These are **analytical conveniences, not ecological or administrative units**. The dashboard
says so on every view that uses them. They exist to demonstrate a user-defined AOI flowing
correctly through weighting, denominators, and uncertainty — which is the real skill being
shown.

Note that 110 + 79 + 129 = 318 > 293. This is not a bug: a 27 km cell straddling 45.5°N is
counted in both bands and contributes to each in proportion to its intersected area. The
*areas* partition exactly; the *cell counts* do not. `pipeline.py` asserts the area partition
at runtime and fails the run if it breaks.

### 1.8 Ensemble replicate ("fold")

Cornell's Trends product ships 100 replicate estimates per cell, from the model's internal
ensemble. They are the product's own uncertainty representation. The dashboard aggregates
**each replicate separately** and then takes quantiles across replicates — see §3.3. The
column is named `fold` in the source data; it means "ensemble member", not "cross-validation
fold". The two senses of *fold* in this project are unrelated:

| Where | Meaning |
|---|---|
| View 02 / `trend_folds.csv` | One of Cornell's 100 ensemble replicates |
| View 03 / `experiment.folds` | One of our 5 spatial cross-validation splits |

### 1.9 Direction: declining / increasing / uncertain

A label derived purely from the 80% interval:

```
upper < 0            → declining
lower > 0            → increasing
interval spans zero  → uncertain
```

"Uncertain" means *the data do not resolve the sign*, not "stable" and not "no change". A
band labelled uncertain may well be changing; this sample cannot tell you which way.

---

## 2. View 01 — Species explorer

> *Explore modeled abundance across Michigan, one week at a time.*

### 2.1 Controls

| Control | Effect |
|---|---|
| **STUDY REGION** | Switches the AOI. Re-weights every metric, re-scopes the map (out-of-region cells drop to 12% opacity and lose focusability), redraws the annual cycle for that region, and clears the selected cell. |
| **SEASON** | Filters to one of the four Status 2023 season windows; jumps the week cursor to the first week of that season and stops playback. |
| **Layer segmented control** | Abundance / Occurrence / Elevation. Changes the values, the color ramp, the units, and the panel title. |
| **Week slider + play** | Steps the 52-week cursor. Play advances one week per second and wraps at 52. |

Playback stops on navigation and on `visibilitychange` — background tabs do not keep
re-rendering. Cells are selectable by mouse **and** by Tab + Enter/Space; the map is a real
focus-managed control, not a picture.

### 2.2 The four metric tiles

**Relative abundance** — area-weighted mean over the selected region for the selected week:

```
mean = Σ(area_km² × estimate) / Σ(area_km² where estimate is finite)
```

Zeros are kept (a modeled zero is information). Missing values are excluded from *both*
numerator and denominator rather than being silently treated as zero — the single most common
way to fabricate a seasonal signal.

**Peak week** — the week with the highest area-weighted mean in the current region. For all
Michigan this is the week of **19 April** at **0.649**. The tile deliberately sits next to a
takeaway that reads *"A seasonal peak is not a population trend"*, because the adjacency of a
peak metric and a trend metric is exactly where people conflate the two.

**Breeding population trend** — pulled from Study A's *other* release (Trends 2022) so the
explorer can show it, but it is computed on a different grid over a different decade. It is
labelled `2012–2022` on the tile for that reason.

**Spatial support** — cell count and supported km², the honesty check behind the mean.

### 2.3 The map

An inline SVG, no mapping library, no tile server — the dashboard works with the network
disconnected.

- **Projection:** a simple cosine-scaled equirectangular projection centered on the Michigan
  window (`project()` in `dist/app.js`). It is a display projection only. **Every area
  computation happens upstream in R in EPSG:8857 (Equal Earth)** — no area is ever derived
  from screen geometry.
- **Cell geometry:** true polygonized native Status cells, clipped to the Michigan boundary.
  Coastal cells are genuinely clipped, which is why shoreline cells look ragged.
- **Color:** sequential green ramp with a √ transform (`color()` in `dist/lib.js`). The
  square root compresses the high tail so that low-but-nonzero cells stay visible; it means
  color is *not* linear in abundance — read values from the inspector, not the ramp.
- **Scale stability:** the maximum is computed across **all weeks**, not per week, so colors
  are comparable as you scrub the timeline. Occurrence is fixed to [0, 1] and elevation to
  [0, 600 m].
- **Region mask:** selecting a band draws its dashed outline and dims cells outside it, while
  keeping them drawn — context is preserved, but only in-region cells are interactive.

### 2.4 The cell inspector

Selecting a cell shows that cell's weekly estimate plus its **pointwise 10–90% interval**
(from Cornell's `lower`/`upper` rasters), occurrence, and mean elevation.

The label is careful: *"Pointwise 10–90% interval"*. It is the uncertainty of **that one cell
in that one week**. There is deliberately **no regional abundance interval anywhere in the
dashboard**, because averaging cell bounds does not produce a valid regional bound — it
ignores the correlation structure between cells and would be indefensibly narrow. Where the
source ships replicate-level data (Trends), the dashboard does propagate uncertainty
properly; where it does not (Status), the dashboard declines to invent it. That asymmetry is
intentional and is worth pointing out to any reviewer.

### 2.5 The annual cycle chart

52 weekly area-weighted means for the current region, with the selected week marked. Every
week is a click/keyboard target. The area fill is decorative; the line is the estimate.

**How to read the current result:** all three bands peak in mid-April (weeks 15–16), not in
the breeding season. For a species that both migrates through and breeds in Michigan, the
April peak reflects **migration passage** — birds moving through inflate the expected count
on a standardized checklist — after which the curve settles to the lower breeding-resident
level (0.239 at week 25, the summer solstice). The northern band peaks highest (1.058) and
the southern band peaks earliest (week 15) and lowest (0.246), consistent with a migration
wave arriving from the south and concentrating toward the breeding range in the north.

That is a defensible reading of the seasonal shape. It is **not** evidence about population
change, which requires view 02.

### 2.6 The elevation layer

Not part of any model in this project. It is WorldClim 2.1 SRTM-derived elevation, cropped
around Michigan and resampled onto the Status grid with `terra::project(..., method =
"average")`. It exists to demonstrate covariate alignment: taking an environmental raster on
a foreign grid and putting it on the biological grid correctly.

Three things the UI states about it:

1. It is **static** — it does not change as you move the week slider.
2. Continuous covariates average; **categorical** covariates (land cover class) would need
   proportion-of-class or modal-class resampling instead. Averaging a land cover code would
   be meaningless.
3. The elevation describes the cell's **native footprint**, while the reported area is
   clipped to the state boundary. At boundary cells these disagree slightly.

It is not used as a predictor and no causal claim is attached to it.

### 2.7 The regional comparison table

Per-band abundance (with an inline bar), supported area, trend, and 80% interval for the
current week. Clicking a band name switches the AOI and scrolls to top. The footnote repeats
the two caveats that matter: intersection-area weighting, and "analytical regions, not
ecological boundaries".

---

## 3. View 02 — Population trends

> *Breeding-season trends from a separate 2012–2022 data product.*

### 3.1 Why this is a separate view

Different release (2022 vs 2023), different grid (sinusoidal vs Equal Earth), different
resolution footprint (156 cells vs 293), different question. The two are **never joined by
row index** — a tempting and catastrophic shortcut, since both are "27 km Michigan cells" and
would silently line up in a spreadsheet. `scripts/spatial.R` reconstructs the trend cell
polygons from cell-center coordinates and half-resolution offsets, transforms them to
EPSG:8857, and intersects them with the same AOIs independently.

The header strip reports the Trends release's own breeding window, **May 24 – August 16**.
Note this differs from Status 2023's breeding season (May 17 – August 16) shown elsewhere:
different releases define their season boundaries independently, and the dashboard shows each
product's own definition rather than harmonizing them into a single misleading window.

### 3.2 What the trend number means

Percent change in relative abundance **per year**, during the breeding season, over 2012–2022.
A value of −0.84 %/yr compounds to roughly −8% over the decade. The source also ships a
cumulative `abd_trend` field, which the cell inspector shows as "Cumulative change".

### 3.3 How the regional number is computed — the key method

This is the most technically interesting computation in the project, and the one most worth
being able to explain from memory.

```
for each ensemble replicate b in 1..100:
    for region R:
        trend_R,b = Σ_cells (abd_ppy_c,b × abd_c,b × area_c∩R) / Σ_cells (abd_c,b × area_c∩R)

regional estimate  = median over b
80% interval       = 10th and 90th percentiles over b
```

Two design decisions are embedded here:

**Weighting by abundance × area.** A cell holding almost no birds should not move the
regional trend as much as a dense one. Area-only weighting would let empty cells with
extreme, noisy percentage changes dominate. This mirrors Cornell's own guidance for regional
trend aggregation.

**Aggregate first, then take quantiles.** The pipeline computes 100 complete regional
summaries and takes quantiles *across those summaries*. It does **not** average the cells'
individual confidence bounds. Averaging bounds would treat cell-level uncertainties as
independent and produce an interval far too narrow to be honest. The science callout on the
view states this in one line: *"Aggregate the ensemble, then quantify uncertainty."*

`pipeline.py` hard-fails the run if any region does not yield exactly 100 complete replicate
summaries, so a partially-missing ensemble cannot quietly narrow the interval.

### 3.4 Reading the current result

| Region | Annual trend | 80% interval | Direction | Cells |
|---|---|---|---|---|
| All Michigan | **−0.84 %/yr** | −1.06 to −0.20 | declining | 156 |
| Northern band | **−1.20 %/yr** | −1.69 to −0.50 | declining | 68 |
| Central band | −0.19 %/yr | −0.56 to **+0.42** | uncertain | 52 |
| Southern band | +0.59 %/yr | **−0.04** to +1.02 | uncertain | 50 |

**The defensible statement:** within this sample's support, breeding-season relative
abundance declined over 2012–2022, and the decline is concentrated in the northern band,
whose interval excludes zero comfortably. The central and southern bands do not resolve a
direction. The southern band's point estimate is positive and its interval only barely
includes zero (−0.04) — suggestive, not conclusive, and the correct thing to say is that it
does not reach the threshold this dashboard uses.

**What you cannot say:** that the south is increasing; that the north-south contrast is
statistically significant (no such comparison was performed); that this describes Michigan as
a whole (this is a teaching subset, not the statewide product); or anything about cause.

### 3.5 The forest plot and the map

The **forest chart** shows each region's median with its 10th–90th percentile bar, against a
dashed zero line. The two "uncertain" bars visibly cross it. This is the clearest single
graphic in the dashboard for the uncertainty story, and the vertical zero line is what makes
it readable.

The **map** uses a diverging red/teal ramp centered on zero, with the scale fixed at ±6 %/yr.
It shows **every** source cell, including cells whose own intervals cross zero. Filtering the
map to "significant" cells would produce a cherry-picked map — one of the standard ways
trend maps mislead. The panel note says so explicitly.

---

## 4. View 03 — Experiment lab

> *A separate checklist experiment · Collared Kingfisher · Singapore, 2012.*

Everything in this view is our own work: our filtering, our features, our models, our
evaluation. Nothing here validates Cornell's Michigan product, and the view carries a
"SEPARATE DATASET" notice saying exactly that.

### 4.1 The question

**Pre-specified:** does adding spatial coordinates and seasonal timing to an effort-only
detection model improve out-of-block prediction of whether a checklist detects Collared
Kingfisher?

Pre-specification matters. Three candidate models were fixed before evaluation; there was no
search over feature sets, no hyperparameter tuning, and no metric shopping. The regularization
strength is fixed at `C = 1.0` and never tuned.

### 4.2 The eligibility funnel

Displayed as a funnel in the view. Each step is a scientific decision, not cleanup:

| Stage | Remaining | Removed | Why |
|---|---|---|---|
| Sampling events | 729 | — | Every sampling event in the auk sample |
| Complete checklists | 729 | 0 | Only `ALL SPECIES REPORTED = 1` can produce a valid zero |
| Stationary / traveling | 237 | **492** | Protocols P21/P22 only — effort is comparable and quantified |
| Effort limits | 204 | 33 | ≤ 300 min, ≤ 5 km, ≤ 10 observers: trims extreme-effort outliers |
| Valid location, date & time | 204 | 0 | Coordinates, parseable date, start hour in [0, 24) |
| Independent shared visits | 204 | 0 | Share groups collapsed to one visit |
| Known observation labels | 204 | 0 | Unapproved records or unparseable counts excluded rather than guessed |

The big cut is the protocol filter. Incidental and area-count checklists have effort that is
either unrecorded or not comparable to a traveling count, so including them would put
uninterpretable effort into an effort-based model.

The **stationary-distance fix** is a detail worth knowing: eBird exports leave `EFFORT
DISTANCE KM` blank for stationary counts. A naive numeric coercion makes those NaN and the
effort filter silently drops every stationary checklist. `checklists.py` sets distance to 0
for P21 before filtering, because a stationary count's distance is genuinely zero, not
unknown.

Result: **204 eligible visits — 67 detections, 137 non-detections, prevalence 32.8%**, across
**23 merged spatial blocks**. Six of the detections are presence-only `X` records: the species
was present but no count was given. They remain detections with an unknown count, which is
correct for a detection model and would be wrong for an abundance model.

### 4.3 The three candidates

| # | Model | Features |
|---|---|---|
| 01 | **Training prevalence** | none — predicts the training fold's detection rate for everything |
| 02 | **Effort only** | log duration, log distance, observers, stationary flag, hour sin/cos |
| 03 | **Effort + space + season** | the above + latitude, longitude, day-of-year sin/cos |

Standardized features into L2-regularized logistic regression (`liblinear`, `C = 1.0`, fixed
seed). Cyclical quantities are encoded as sin/cos pairs so that 23:00 and 01:00 are adjacent
rather than 22 units apart.

Model 01 is the **baseline that makes the other two interpretable**. A model that cannot beat
"always predict the base rate" has learned nothing, and reporting the other two without it
would be uninformative.

### 4.4 The evaluation design

5-fold `GroupKFold` grouped on merged spatial blocks. Every fold trains on ~163 visits and
tests on ~40. Two assertions run inside the fold loop and abort the pipeline on violation:

```python
assert not set(groups[train]) & set(groups[test]),                      "Spatial leakage"
assert not set(train localities) & set(test localities),                "Locality leakage"
```

Leakage guards as executable assertions rather than prose is the point: the claim "no
spatial leakage" is enforced by the code, not by the author's memory.

Fold composition is published because it is the main weakness of a 204-row study:

| Fold | Train | Test | Test detections | Test blocks |
|---|---|---|---|---|
| 1 | 163 | 41 | 16 | 4 |
| 2 | 163 | 41 | 10 | 4 |
| 3 | 163 | 41 | 19 | 5 |
| 4 | 163 | 41 | **6** | 5 |
| 5 | 164 | 40 | 16 | 5 |

Fold 4 holds six detections. Any metric from a fold that thin is volatile, and that is
precisely why the conclusion below rests on an interval rather than a point estimate.

### 4.5 The metrics

All computed on **out-of-fold predictions**: each visit is scored only by a model that never
saw its spatial block.

| Metric | Direction | What it captures |
|---|---|---|
| **Brier score** | lower | Mean squared error of the probability. Rewards being both right and calibrated. The primary metric here. |
| **ROC AUC** | higher | Ranking quality: probability a random detection is ranked above a random non-detection. Chance = 0.5. |
| **Average precision** | higher | Area under precision-recall; more informative than AUC when detections are the minority class. |
| **Log loss** | lower | Penalizes confident errors severely. |

Results:

| Candidate | Brier ↓ | ROC AUC ↑ | Avg. precision ↑ | Log loss ↓ |
|---|---|---|---|---|
| Training prevalence | **0.2282** | 0.356 | 0.268 | **0.6503** |
| Effort only | 0.2293 | **0.553** | 0.386 | 0.6615 |
| Effort + space + season | 0.2351 | 0.545 | **0.395** | 0.6860 |

**Why the baseline's AUC is 0.356, below chance.** A constant predictor has no ranking
information at all; its AUC is an artifact of tie-handling across folds with slightly
different training prevalences, not a signal. It should be read as "undefined", not as
"anti-predictive". Its *Brier* and *log loss*, which do not depend on ranking, are the
meaningful baseline numbers — and they are the best in the table.

**The honest summary:** both fitted models rank better than chance (AUC ≈ 0.55, average
precision 0.39–0.40 against a 0.33 base rate), but neither beats the constant baseline on
calibrated probability accuracy. On a 204-visit sample, effort and location carry a little
ranking signal and not enough to improve the probabilities.

### 4.6 The comparison test, and the verdict

The view compares models 02 and 03 only — the pre-specified question — using a **paired
spatial-block bootstrap** of the per-visit squared-error difference:

```
δ_i   = (y_i − p_i,space_time)² − (y_i − p_i,effort)²
resample the 23 blocks with replacement, 500 times, take mean(δ) each time
report the 2.5th and 97.5th percentiles
```

Result: **Δ Brier = +0.0059, 95% interval −0.0089 to +0.0216.**

Three properties of this test:

- **Paired** — the same visits score both models, so visit-level difficulty cancels.
- **Block-resampled** — resampling whole spatial blocks respects spatial correlation.
  Resampling individual visits would treat nearby checklists as independent and produce an
  interval that is too narrow.
- **Predictions held fixed** — the out-of-fold predictions are not refit inside the bootstrap.
  This quantifies uncertainty in the *comparison given these fitted models*; it does not
  include model-fitting variability. That is a stated limitation, not an oversight.

The interval spans zero, so the view reports **"No clear improvement"**. The sign is positive
(space/season was slightly *worse*), but the interval is wide enough that the correct
conclusion is that this sample cannot resolve the question.

**This is a real negative result, reported as one.** It would have been easy to search
feature sets until something looked positive. The value on display is the discipline of
pre-specification plus honest reporting, and the willingness to ship a dashboard whose
headline experimental finding is "we could not tell".

### 4.7 The calibration chart

Predicted probability (x) against observed detection frequency (y) in five bins, with point
size ∝ √n, against the diagonal. Perfect calibration sits on the diagonal.

Both fitted models sit **above the diagonal at low predictions and below it at high ones** —
the classic under-confident-then-over-confident S. Effort-only predicts 0.148 for a bin that
actually detects at 0.292, and predicts 0.651 for a bin that detects at 0.400. The
highest-confidence bin of the space+season model contains a **single visit** predicted at 0.82
that was a non-detection, which is why its curve collapses to zero at the right edge.

That single point is the visual argument for the whole evaluation design: at this sample size,
the tail bins are individual birds and individual mornings. Read the big circles, ignore the
small ones, and trust the bootstrap interval over any of them.

---

## 5. View 04 — Data products

> *Create a regional extract, inspect it, and take the provenance with you.*

The deliverable view: build an extract, preview it, download it with its lineage attached.

### 5.1 The builder

| Choice | Options |
|---|---|
| Product | Weekly status summaries · Regional breeding trends |
| Region | Michigan + all three bands · Michigan · any single band |
| Season | Full annual cycle · four Status seasons (disabled for trends — a decade-long breeding trend has no weekly season filter) |
| Format | CSV · JSON |

Season filtering uses month-day comparison with wraparound, so the nonbreeding season
(22 Nov – 8 Mar) correctly spans the year boundary (`seasonFor()` in `dist/lib.js`).

### 5.2 Provenance travels with the data

Every JSON download embeds a manifest:

```json
{
  "run_id": "ed1cad1e208f",
  "species": "yebsap-example",
  "region": "north",
  "product": "weekly",
  "season": "breeding",
  "rows": 52,
  "created_at": "...",
  "source_versions": { "status": 2023, "trends": 2022 },
  "interval": "No regional interval inferred from cell intervals"
}
```

That last field ships the epistemics with the file. A weekly extract carries a statement
saying no regional interval is claimed; a trends extract carries `"80% ensemble interval"`.
Someone who receives the CSV six months later, with no access to this dashboard, still knows
what they may and may not do with it.

CSV cannot embed a manifest, so the view provides a **selection manifest** button that
downloads the companion JSON, and the post-download toast tells you to use it. That is the
deliberate handling of a format limitation rather than silently dropping the lineage.

### 5.3 The other downloads

| File | Contents |
|---|---|
| `conservation-brief.html` | Generated print-ready brief: question, results, interpretation, methods, limitations, citations. Numbers are interpolated from the run, so the prose cannot drift from the data. |
| `provenance.json` | The full run manifest — see §7. |
| `model-evaluation.json` | The complete experiment block: folds, all metrics, calibration bins, bootstrap interval. |
| `weekly-regions.csv` / `regional-trends.csv` | The two tabular products at 7 decimal places. |
| `figures/annual-cycle.png`, `figures/regional-trends.png` | Standalone R-rendered figures for slides and documents. |

---

## 6. View 05 — Methods & lineage

The provenance view. Four things live here.

**The five-stage pipeline diagram** — Acquire → Validate → Analyze → Package → Communicate —
with the architectural claim underneath: the browser explores **precomputed** products; R and
Python do the science locally; the hosted page runs no large jobs and touches no private
observations.

**The scientific contract** — expandable statements of the four facts that constrain every
reading: relative abundance is not population size; seasonality and trends are separate
products; areas and missing support drive the denominators; analytical bands are not
ecological units.

**The benchmark** — 15,236 cell-week rows aggregated two ways: in-memory pandas at **1.88 ms**
median, DuckDB over warm local Parquet at **1.21 ms** median, over 5 repetitions, with results
asserted numerically equivalent at `rtol=1e-9`. Parquet size 164 KiB (ZSTD).

Read the scope line carefully, because it is the point of including it: *"Small-sample
aggregation only… No large-scale performance claim."* These are different I/O paths at
teaching scale. The honest claim is "two engines, same answer, measured" — not "DuckDB is
1.6× faster". Someone who quotes this as a performance result has misread it, and the
dashboard says so on screen. The repository also ships a SLURM template and a scaling plan,
both explicitly marked as **not executed**.

**Data lineage** — every primary source with its release, DOI, and terms.

---

## 7. What happens behind the dashboard

The browser does no science. It reads five static files from `dist/data/` and renders them.
Everything else happens in a two-language local pipeline.

### 7.1 Stage 1 — `scripts/spatial.R`

Runs first, and does everything that needs the raster/vector toolchain.

1. **Version gate.** Compares the installed `ebirdst` release against `config/analysis.json`
   and stops the run on mismatch. A silent release upgrade would change the numbers
   underneath the conclusions, so it is made loud.
2. **AOI construction.** Michigan from Natural Earth, made valid, transformed to EPSG:8857.
   The three bands are built as latitude boxes and intersected with the state.
3. **Bounded raster reads.** `terra::crop(..., snap = "out")` restricts each source raster to
   the AOI **on disk, before any 52-layer array is materialized**. This is the memory
   discipline that lets the same code shape scale to continental rasters.
4. **Validation.** `compareGeom` across the abundance/lower/upper/occurrence stacks; 52 layers
   asserted; abundance ≥ 0; occurrence in [0, 1]; and `lower ≤ median ≤ upper` checked
   elementwise. A bad source file fails here, not silently downstream.
5. **Polygonization and weighting.** Cells with a finite estimate in ≥ 1 week are polygonized,
   clipped to Michigan, and intersected with the bands. Intersection areas in km² become the
   weights.
6. **Elevation alignment.** WorldClim 10-arcmin elevation cropped and projected onto the
   Status grid with area-averaging.
7. **Trends, independently.** Source cell polygons reconstructed from cell centers ±
   half-resolution, transformed to EPSG:8857, intersected with the same AOIs. No Status
   identifier or value enters this path.
8. **Outputs.** `weekly.csv`, `cells.csv`, `weights.csv`, `trends.csv`, `trend_folds.csv`,
   `trend_weights.csv`, GeoJSON cell layers, a GeoPackage, two GeoTIFFs, and `metadata.json`.

### 7.2 Stage 2 — `scripts/run_pipeline.py` → `src/fieldwork/pipeline.py`

1. **Input integrity.** SHA-256 of every raw input compared against `data/manifest.lock.json`.
   A mismatch **stops the run** and names the changed files. Refreshing data is therefore a
   deliberate, reviewable act — you must update the lock on purpose.
2. **Spatial cache fingerprint.** SHA-256 over (input hashes + `spatial.R` + config). With
   `--skip-spatial`, R is skipped **only** if the fingerprint matches; otherwise the run
   aborts rather than reusing stale products.
3. **Contract checks.** No duplicate cell-weeks. Region weights must sum to cell areas within
   `rtol=1e-6` — i.e. the bands must genuinely partition the supported footprint.
4. **Summaries.** `products.py` computes area-weighted weekly means and the
   aggregate-then-quantile trend summaries, asserting 100 replicates per region.
5. **Checklists and experiment.** `checklists.py` builds the eligible denominator;
   `evaluation.py` runs the spatial CV, the three candidates, calibration, and the paired
   block bootstrap.
6. **Benchmark.** pandas vs DuckDB with numerical equivalence asserted.
7. **Run identity.** `run_id` = first 12 hex of SHA-256 over (all input hashes + all source
   file hashes). The ID changes if the data changes *or* the code changes — so a run ID
   pins a complete computational state, not just a dataset.
8. **Publication.** Atomic JSON writes (temp file + `replace`), non-finite floats normalized
   to `null` with `allow_nan=False` so no `NaN` can enter the JSON, and everything written to
   `dist/data/` and `dist/downloads/`.
9. **Communication.** The conservation brief is generated with interpolated numbers, and
   `scripts/figures.R` renders the standalone PNGs.

### 7.3 What is deliberately not published

`outputs/private/` holds `eligible_checklists.csv` and `oof_predictions.csv` — the row-level
checklist frame and per-visit predictions. These stay local and are gitignored. Nothing in
`dist/` contains observer identifiers, checklist identifiers, locality names, or exact
observation coordinates. The web layer carries only transformed derived products.

---

## 8. Data contract: `dist/data/analysis.json`

One versioned file drives the whole dashboard.

| Key | Shape | Notes |
|---|---|---|
| `schema_version` | `1` | Bump on any breaking shape change |
| `run` | id, created_at, seed, elapsed_seconds | Shown in the UI as the run badge |
| `metadata` | species, versions, both CRS strings, cell counts, season dates, R + package versions | |
| `regions` | 3 band definitions | Straight from config |
| `weekly_summary` | 208 rows = 4 regions × 52 weeks | region, week, date, abundance, occurrence, supported_area_km2, support_fraction, cells |
| `regional_trends` | 4 rows | region, annual_percent, lower, upper, folds, direction, cells |
| `checklists` | funnel + counts | Singapore summary |
| `experiment` | design, folds, models, comparison | `status` is `complete` or `insufficient_data` |
| `benchmark` | timings + scope string | |

The two GeoJSON layers carry per-cell arrays (`abundance`, `lower`, `upper`, `occurrence` —
52 elements each) plus a `regions` membership array, so the map can re-render any week without
another fetch.

`experiment.status` is a real branch: if a future dataset yields fewer than 30 visits, fewer
than 3 blocks, or only one label class, `evaluate()` returns `insufficient_data` and the view
renders an explanation instead of metrics. The dashboard degrades into an honest statement
rather than reporting numbers computed from too little data.

---

## 9. Every kind of uncertainty in this dashboard, and where it comes from

Four distinct things, all sometimes called "the error bars". Keeping them apart is most of
the interpretive skill this dashboard demonstrates.

| # | Uncertainty | Where shown | Source | Scope |
|---|---|---|---|---|
| 1 | **Cell-week pointwise 10–90% interval** | Explorer cell inspector | Cornell's `lower`/`upper` rasters | One cell, one week. Never aggregated. |
| 2 | **Cell trend 80% interval** | Trends cell inspector | Source `abd_ppy_lower`/`upper` | One cell, 2012–2022 |
| 3 | **Regional trend 80% interval** | Trends metrics, forest chart, regional table | 10th/90th percentiles across 100 **aggregated** ensemble replicates | One region |
| 4 | **Δ Brier 95% interval** | Experiment lab | 500-replicate paired spatial-block bootstrap | Model comparison, Singapore only |

Note what is **absent**: there is no regional *abundance* interval anywhere, because the
Status product does not ship replicate-level data that would let one be computed honestly.
The dashboard could have averaged cell bounds and produced a plausible-looking band. It
refuses, and says why. The presence of #3 and the absence of a regional abundance interval,
side by side, is the clearest demonstration in the project that uncertainty is being
propagated rather than decorated.

---

## 10. Limitations — the list to volunteer, not defend

1. **Teaching subsets, both of them.** `yebsap-example` is a restricted published sample, not
   Cornell's full Michigan product. Every Michigan number describes the sample's support.
2. **Two species, two continents, one interface.** By design, but it means neither study
   generalizes to the other.
3. **204 visits, 23 blocks, 67 detections.** Small. Fold 4 holds six detections. The negative
   result is a statement about this sample, not about detection modeling.
4. **Bootstrap holds predictions fixed** — it excludes model-fitting variability.
5. **27 km cells are coarse.** Values are treated as uniform within a cell, including across
   coastlines. This is not habitat mapping and cannot support parcel-level decisions.
6. **Natural Earth is a generalized political boundary**, not a surveyed shoreline. Supported
   area is not terrestrial habitat area.
7. **No causal claims.** Elevation is displayed, not modeled. Nothing here identifies *why*
   the northern band declined.
8. **The benchmark is teaching-scale.** No large-data performance claim is made or supported.
9. **SLURM template and CI workflow are unexecuted templates**, stated as such in `REVIEW.md`.
10. **Regional trend directions use an 80% interval**, a deliberately stated threshold rather
    than a hypothesis test, and no between-region comparison was performed.

---

## 11. Anticipated questions, with answers

**"Why is the peak in April rather than the breeding season?"**
Migration passage. Migrants moving through inflate the expected count on a standardized
checklist before the population settles to its breeding-resident level. It is a detectability-
and-movement pattern in a within-year product, and it says nothing about population change.

**"Your headline trend is −0.84%/yr but the south is +0.59%/yr. Isn't that contradictory?"**
No. The Michigan-wide figure is abundance-and-area weighted, so the northern band — higher
abundance, larger supported area, and clearly declining — dominates it. The southern estimate
is positive but its interval includes zero, so it does not establish an increase. The correct
reading is "a decline concentrated in the north, with the south unresolved".

**"Why not average the cell confidence bounds to get a regional interval?"**
Because it assumes cell-level errors are independent, and they are not. The result would be
far too narrow. Where the source ships replicates (Trends), the pipeline aggregates each
replicate and takes quantiles across the 100 regional summaries. Where it does not (Status),
no regional interval is claimed.

**"Your best model doesn't beat a constant baseline. Why ship it?"**
Because that is the result. The question was pre-specified, three candidates were fixed in
advance, there was no tuning, and the paired block bootstrap interval spans zero. Reporting
"no clear improvement" is the correct output of that design. Suppressing it, or searching
features until something looked positive, would be the failure.

**"The baseline's AUC is 0.356, below chance. Is that a bug?"**
No — a constant predictor has no ranking information, so its AUC is a tie-handling artifact
across folds with slightly different training prevalences. It should be read as undefined.
Its Brier score and log loss, which do not depend on ranking, are the meaningful baseline
numbers, and they are the best in the table.

**"How do you know there's no spatial leakage?"**
Two assertions inside the fold loop abort the pipeline if any spatial block or any locality
ID appears in both training and test. 0.05° blocks are merged by shared `LOCALITY ID` first,
so a hotspot straddling a block boundary cannot split across folds.

**"Why 492 of 729 checklists discarded at one step?"**
The protocol filter. Only stationary (P21) and traveling (P22) counts have quantified,
comparable effort. Incidental and area counts do not, and feeding them into an effort-based
model would put uninterpretable effort on the right-hand side.

**"Why two languages?"**
R for provider-supported data access (`ebirdst`, `auk`) and the mature raster/vector stack
(`terra`, `sf`); Python for evaluation, products, and orchestration. The boundary is
documented files — CSV, GeoJSON, GeoTIFF, Parquet — not a fragile in-process bridge, so each
stage is independently inspectable and testable. `docs/ARCHITECTURE.md` ADR 2 records the
tradeoff and the all-R and all-Python alternatives.

**"What stops the numbers drifting from the documentation?"**
The conservation brief interpolates its figures from the run, so the prose cannot disagree
with the data. The run ID hashes inputs *and* source, so any change to either produces a new
ID. Input checksum mismatches stop the run. And the pipeline hard-fails on contract
violations — duplicate cell-weeks, region weights that don't partition the footprint, or
fewer than 100 ensemble replicates.

**"Could this scale?"**
The shape is designed to: crop-before-read bounds memory at the AOI, the compute/serve split
means the browser never runs a large job, and Parquet plus DuckDB is the natural growth path
for the tabular stage. But nothing here is *evidence* of scale. The benchmark is teaching-
scale and the SLURM template is unexecuted, both stated on the page.

---

## 12. Verifying any of this yourself

```bash
make setup       # .venv + R libraries into .R-library
make fetch       # Rscript scripts/fetch_data.R — official samples
make pipeline    # R spatial stage, then the Python pipeline
make test        # 18 Python tests, 5 JS tests, JS syntax check
make serve       # http://127.0.0.1:4173
```

`make reproduce` runs fetch → pipeline → test in order. The run ID printed at the end should
be `ed1cad1e208f` for the pinned inputs; if it differs, something in the inputs or the source
changed, and the manifest diff will tell you what.

`docs/REVIEW.md` carries the twelve-step manual acceptance walkthrough — including the offline
check (disconnect the network; maps, charts, and data must still load) and the accessibility
pass (200% text zoom, keyboard-only cell selection, narrow viewport).
