# Review and acceptance checklist

## Completed locally

- Downloaded official Cornell Status/Trends and checklist samples plus Natural Earth and WorldClim sources.
- Executed R raster/vector workflow and Python product/evaluation pipeline successfully.
- Rendered standalone scientific figures from exported summaries.
- Passed 18 Python scientific/data-contract tests and 5 JavaScript export/helper tests.
- Passed frontend JavaScript syntax checks.
- Confirmed local HTTP response: 200.

No connected browser was available in the build session. Browser interaction/visual checks below are a manual acceptance list, not claimed test results. GitHub Actions and SLURM execution are also unverified environments.

## Five-minute manual frontend check

1. Open http://127.0.0.1:4173 after starting the local server. The first view should show real Michigan grid cells and the annual-cycle curve.
2. Move the timeline to week 16 (April 19), then week 25 (June 21). Check the date, map colors, current mean and selected chart point.
3. Change to Northern band; verify the selected region, supported area and weighted mean. Restore all Michigan.
4. Switch abundance, occurrence and elevation layers; verify labels/units and the corresponding legend. Elevation is static across weeks.
5. Select a cell by mouse and with keyboard Tab + Enter. Inspect its interval, occurrence and elevation. No cell-level interval should be labeled a regional interval.
6. Play the annual cycle, pause it, and navigate away. Playback should stop on navigation or when the document becomes hidden.
7. Open Population trends. Check the 2012–2022 label and annual percentage units. Confirm that uncertain regional intervals visibly cross zero.
8. Open Experiment lab. Check the Singapore/Collared Kingfisher context, 204 eligible visits, three candidates and the uncertainty statement.
9. Export Northern band + breeding weekly data as JSON. Confirm every record has `region=north`, a breeding date and a manifest identifying the run. For CSV, use the selection-manifest button to download its companion metadata.
10. Open the conservation brief, provenance and scientific figures. Print the brief if a PDF backup would help.
11. Resize to a narrow screen and zoom text to 200%. Check all controls, readable labels, table scrolling and navigation.
12. Disconnect internet after starting the local server. Maps, charts and data should still load; external citation pages will not.

## Scientific/code review checklist

- Are the ecological question, estimand, eligibility criteria and product scope explicit?
- Do EBD and sampling-event extracts refer to the same time/region/taxonomic scope?
- Are shared-checklist groups, observation quality flags and unknown counts handled correctly?
- Are grid CRS, alignment, nodata and zero values preserved?
- Does an AOI change alter weights and denominators as intended?
- Are Status and Trends releases and grids kept distinct?
- Are regional uncertainty summaries calculated from aligned source replicates?
- Do preprocessing and any future tuning happen inside training folds?
- Do train/test spatial groups and localities overlap? Are observer and temporal leakage evaluated?
- Do source changes require a deliberate checksum and dependency-lock update?
- Are raw data, credentials and sensitive fields excluded from the published bundle?
- Are assumptions, negative results, benchmark scope and unsupported uses communicated?

## Suggested review workflow

Use a branch for changes, keep scientific changes small enough to review, include the question and acceptance criteria in the pull request, regenerate products when scientific source changes, and attach validation plus a short result interpretation. In a shared repository, require a scientific reviewer for weighting/sampling/model changes and a software reviewer for orchestration/publishing changes. Those reviews are a proposed practice; no outside review is claimed for this prototype.
