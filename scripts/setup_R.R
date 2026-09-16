#!/usr/bin/env Rscript
# Install dependencies in a project-local library, never replace a system library.
dir.create(".R-library", showWarnings = FALSE)
.libPaths(c(normalizePath(".R-library"), .libPaths()))
options(repos = c(CRAN = "https://cloud.r-project.org"))
if (!requireNamespace("renv", quietly = TRUE)) install.packages("renv", lib = ".R-library")
renv::restore(lockfile = "renv.lock", library = ".R-library", prompt = FALSE)
cat("R packages installed. R scripts add .R-library automatically when present.\n")
