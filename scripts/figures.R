#!/usr/bin/env Rscript
# Standalone scientific figures generated from the same exported summaries as the UI.
d <- read.csv("dist/downloads/weekly-regions.csv")
t <- read.csv("dist/downloads/regional-trends.csv")
cols <- c(all = "#162f35", north = "#0072B2", central = "#009E73", south = "#D55E00")
labels <- c(all = "Michigan", north = "Northern band", central = "Central band", south = "Southern band")
dir.create("dist/downloads/figures", showWarnings = FALSE, recursive = TRUE)
png("dist/downloads/figures/annual-cycle.png", width = 1600, height = 950, res = 150, type = "cairo")
par(mar = c(7, 5, 4, 2), family = "sans", las = 1)
plot(NA, xlim = c(1,52), ylim = c(0,max(d$abundance)*1.12), xaxt = "n",
     xlab = "Week of the annual cycle (Status 2023)", ylab = "Area-weighted relative abundance",
     main = "Yellow-bellied Sapsucker: Michigan annual cycle", bty = "l")
axis(1, at = c(1,14,27,40,52), labels = c("January", "April", "July", "October", "December"))
grid(nx = NA, ny = NULL, col = "#e4e8e5", lty = 1)
for (r in names(cols)) {s <- d[d$region == r, ]; lines(s$week, s$abundance, col = cols[r], lwd = ifelse(r == "all",3,2), lty = match(r,names(cols)))}
legend("topright", legend = labels, col = cols, lty = 1:4, lwd = c(3,2,2,2), bty = "n")
mtext("Source: Cornell ebirdst teaching sample. Bands at 44 and 45.5 degrees N. Not population size.", side = 1, line = 5.3, cex = .72)
dev.off()
png("dist/downloads/figures/regional-trends.png", width = 1600, height = 950, res = 150, type = "cairo")
par(mar = c(8, 10, 4, 3), family = "sans", las = 1)
y <- seq_len(nrow(t))
plot(t$annual_percent, y, xlim = range(c(t$lower,t$upper))*1.18, ylim = c(.5,nrow(t)+.5),
     yaxt = "n", ylab = "", xlab = "Annual change in relative abundance (%)", pch = 19,
     col = cols[t$region], cex = 1.4, bty = "l", main = "Breeding trends, 2012–2022: regional ensemble uncertainty")
abline(v = 0, col = "#89978a", lty = 2)
segments(t$lower,y,t$upper,y,col = cols[t$region],lwd = 3)
points(t$annual_percent,y,pch = 21,bg = cols[t$region],col = "white",cex = 1.8)
axis(2,at = y,labels = labels[t$region],tick = FALSE)
mtext("Median and 80% interval across 100 source ensemble replicates; abundance x area weighted.",side = 1,line = 5.1,cex = .75)
mtext("Source: Cornell ebirdst Trends 2022 teaching sample. Not a parcel-scale conservation ranking.",side = 1,line = 6.2,cex = .7)
dev.off()
