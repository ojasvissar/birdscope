#!/usr/bin/env Rscript
# Official teaching data only. Full species downloads require the user's own key.
options(timeout = 300)
if (dir.exists(".R-library")) .libPaths(c(normalizePath(".R-library"), .libPaths()))
suppressPackageStartupMessages(library(ebirdst))
dir.create("data/raw", recursive = TRUE, showWarnings = FALSE)
ebirdst_download_status("yebsap-example", path = "data/raw", download_all = TRUE,
                       show_progress = TRUE)
ebirdst_download_trends("yebsap-example", path = "data/raw", show_progress = TRUE)
base <- "https://raw.githubusercontent.com/CornellLabofOrnithology/auk/main/inst/extdata/"
for (name in c("zerofill-ex_ebd.txt", "zerofill-ex_sampling.txt")) {
  dest <- file.path("data/raw", name)
  if (!file.exists(dest)) download.file(paste0(base, name), dest, mode = "wb")
}
# Natural Earth administrative boundaries: public domain, contextual map only.
url <- paste0("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/",
              "geojson/ne_50m_admin_1_states_provinces.geojson")
if (!file.exists("data/raw/states.geojson")) {
  download.file(url, "data/raw/states.geojson", mode = "wb")
}
capture.output(sessionInfo(), file = "data/raw/R-session.txt")
elev <- "data/raw/wc2.1_10m_elev.zip"
if (!file.exists(elev)) download.file(
  "https://geodata.ucdavis.edu/climate/worldclim/2_1/base/wc2.1_10m_elev.zip",
  elev, mode = "wb")
cat("Official samples downloaded. Raw inputs remain local and are gitignored.\n")
