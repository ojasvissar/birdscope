#!/usr/bin/env Rscript
# Memory-bounded at the AOI: crop on disk before materializing any 52-layer array.
if (dir.exists(".R-library")) .libPaths(c(normalizePath(".R-library"), .libPaths()))
suppressPackageStartupMessages({library(ebirdst); library(terra); library(sf); library(jsonlite)})
options(warn = 1)
terraOptions(memfrac = 0.4, progress = 0)
started <- proc.time()[["elapsed"]]
cfg <- fromJSON("config/analysis.json")
if (as.integer(ebirdst_version()$status_version_year) != cfg$status_version ||
    as.integer(ebirdst_version()$trends_version_year) != cfg$trends_version) {
  stop("ebirdst release does not match config. Install the pinned version or migrate explicitly.")
}
dir.create("outputs/spatial", recursive = TRUE, showWarnings = FALSE)
dir.create("dist/data", recursive = TRUE, showWarnings = FALSE)
states <- st_read("data/raw/states.geojson", quiet = TRUE)
mi <- st_make_valid(states[states$name == cfg$region & states$admin == "United States of America", "name"])
stopifnot(nrow(mi) == 1)
mi_ea <- st_transform(mi, 8857)
write_geo <- function(x, file) {
  st_write(st_transform(x, 4326), file, driver = "GeoJSON", delete_dsn = TRUE, quiet = TRUE,
           layer_options = "COORDINATE_PRECISION=5")
}
context <- states[states$name %in% c("Michigan", "Wisconsin", "Minnesota", "Illinois",
                                    "Indiana", "Ohio", "Ontario"), "name"]
context <- suppressWarnings(st_crop(context, c(xmin = -93, ymin = 40.5, xmax = -80, ymax = 49)))
context <- st_transform(st_simplify(st_transform(context, 8857), dTolerance = 1200), 4326)
write_geo(context, "dist/data/basemap.geojson")

# Explicit analytical bands, clipped to Michigan. These are not administrative regions.
boxes <- lapply(seq_len(nrow(cfg$regions)), function(i) {
  r <- cfg$regions[i, ]; xy <- matrix(c(-92, r$south, -81, r$south, -81, r$north,
                                      -92, r$north, -92, r$south), ncol = 2, byrow = TRUE)
  st_polygon(list(xy))
})
regions <- st_sf(region = cfg$regions$id, name = cfg$regions$name,
                 geometry = st_sfc(boxes, crs = 4326))
regions <- suppressWarnings(st_intersection(st_transform(regions, 8857), st_geometry(mi_ea)))
write_geo(regions, "dist/data/regions.geojson")
write_geo(regions, "outputs/spatial/regions.geojson")

load_cropped <- function(product = "abundance", metric = "median") {
  r <- load_raster(cfg$species, product = product, metric = metric,
                   resolution = "27km", path = "data/raw")
  crop(r, vect(st_transform(mi, crs(r))), snap = "out")
}
abd <- load_cropped()
lower <- load_cropped(metric = "lower")
upper <- load_cropped(metric = "upper")
occ <- load_cropped(product = "occurrence")
stopifnot(compareGeom(abd, lower), compareGeom(abd, upper), compareGeom(abd, occ), nlyr(abd) == 52)
av <- values(abd); lv <- values(lower); uv <- values(upper); ov <- values(occ)
stopifnot(all(av[is.finite(av)] >= 0), all(ov[is.finite(ov)] >= 0 & ov[is.finite(ov)] <= 1))
stopifnot(all(lv <= av | is.na(lv) | is.na(av)), all(av <= uv | is.na(av) | is.na(uv)))
valid <- rowSums(is.finite(av)) > 0
index <- abd[[1]]; values(index) <- ifelse(valid, seq_len(ncell(index)), NA_real_)
names(index) <- "cell_id"
cells <- st_as_sf(as.polygons(index, aggregate = FALSE, na.rm = TRUE))
cells <- suppressWarnings(st_intersection(st_make_valid(cells), st_geometry(mi_ea)))
cells$area_km2 <- as.numeric(st_area(cells)) / 1e6
cells <- cells[cells$area_km2 > 0.001, ]
weights <- suppressWarnings(st_intersection(cells[, "cell_id"], regions[, "region"]))
weights$area_km2 <- as.numeric(st_area(weights)) / 1e6
write.csv(st_drop_geometry(weights), "outputs/spatial/weights.csv", row.names = FALSE)

# An actual SRTM-derived elevation raster, aligned to the biological grid.
unzip("data/raw/wc2.1_10m_elev.zip", exdir = "data/raw/elevation")
elev <- rast("data/raw/elevation/wc2.1_10m_elev.tif")
elev <- crop(elev, ext(-92, -81, 41, 49))
aligned <- project(elev, abd[[1]], method = "average")
cells$elevation_m <- values(aligned)[cells$cell_id, 1]
centers <- st_coordinates(st_transform(st_centroid(st_geometry(cells)), 4326))
cells$longitude <- centers[, 1]; cells$latitude <- centers[, 2]
write_geo(cells, "outputs/spatial/status_cells.geojson")
write.csv(st_drop_geometry(cells), "outputs/spatial/cells.csv", row.names = FALSE)
dates <- as.character(as.Date(names(abd)))
long <- do.call(rbind, lapply(seq_len(nlyr(abd)), function(w) {
  id <- cells$cell_id
  data.frame(cell_id = id, week = w, date = dates[w], abundance = av[id, w],
             lower = lv[id, w], upper = uv[id, w], occurrence = ov[id, w])
}))
write.csv(long, "outputs/spatial/weekly.csv", row.names = FALSE, na = "")
writeRaster(abd, "outputs/spatial/michigan_weekly_abundance.tif", overwrite = TRUE,
            gdal = c("COMPRESS=DEFLATE", "TILED=YES"))
writeRaster(aligned, "outputs/spatial/elevation_aligned.tif", overwrite = TRUE,
            gdal = c("COMPRESS=DEFLATE", "TILED=YES"))

# Trends have a DIFFERENT grid/projection and release. Never join them by row index.
tr <- load_trends(cfg$species, path = "data/raw")
folds <- load_trends(cfg$species, fold_estimates = TRUE, path = "data/raw")
tr_grid <- rasterize_trends(tr)
pts <- st_as_sf(tr, coords = c("longitude", "latitude"), crs = 4326, remove = FALSE)
xy <- st_coordinates(st_transform(pts, crs(tr_grid)))
dx <- res(tr_grid)[1] / 2; dy <- res(tr_grid)[2] / 2
polygons <- lapply(seq_len(nrow(tr)), function(i) {
  x <- xy[i, 1]; y <- xy[i, 2]
  st_polygon(list(matrix(c(x-dx,y-dy, x+dx,y-dy, x+dx,y+dy, x-dx,y+dy,
                           x-dx,y-dy), ncol=2, byrow=TRUE)))
})
tr_cells <- st_sf(tr, geometry = st_sfc(polygons, crs = st_crs(crs(tr_grid))))
tr_cells <- st_transform(tr_cells, 8857)
tw <- suppressWarnings(st_intersection(tr_cells[, "srd_id"], regions[, "region"]))
tw$area_km2 <- as.numeric(st_area(tw)) / 1e6
write.csv(st_drop_geometry(tw), "outputs/spatial/trend_weights.csv", row.names = FALSE)
write.csv(tr, "outputs/spatial/trends.csv", row.names = FALSE)
write.csv(folds, "outputs/spatial/trend_folds.csv", row.names = FALSE)
tr_cells <- suppressWarnings(st_intersection(tr_cells, st_geometry(mi_ea)))
write_geo(tr_cells, "outputs/spatial/trend_cells.geojson")
write_sf(st_transform(tr_cells, 5070), "outputs/spatial/trends.gpkg", delete_dsn = TRUE, quiet = TRUE)
config <- load_config(cfg$species, path = "data/raw")
metadata <- list(status_version = cfg$status_version, trends_version = cfg$trends_version,
  species = "Yellow-bellied Sapsucker", scientific_name = "Sphyrapicus varius",
  status_crs = crs(abd, proj = TRUE), trends_crs = crs(tr_grid, proj = TRUE),
  status_cells = nrow(cells), trend_cells = nrow(tr_cells), weeks = 52,
  season_dates = config$season_dates, r_version = R.version.string,
  packages = lapply(c("ebirdst", "terra", "sf", "jsonlite"), function(p) {
    list(name = p, version = as.character(packageVersion(p)))
  }), elapsed_seconds = unname(proc.time()[["elapsed"]] - started))
write_json(metadata, "outputs/spatial/metadata.json", auto_unbox = TRUE, pretty = TRUE)
cat(sprintf("Spatial products complete: %d status cells; %d trend cells; %.1f seconds.\n",
            nrow(cells), nrow(tr_cells), metadata$elapsed_seconds))
