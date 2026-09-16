#!/bin/bash
#SBATCH --job-name=fieldwork-ebird
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=outputs/slurm-%j.log
set -euo pipefail
# Submit from the repository root after installing dependencies and staging data:
# mkdir -p outputs
# sbatch hpc/analysis.slurm
# Module names are cluster-specific; activate your R/Python environment here.
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-2}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export VECLIB_MAXIMUM_THREADS="$OMP_NUM_THREADS"
.venv/bin/python scripts/run_pipeline.py
# Intentionally a single job: never run concurrent writers against dist/ or outputs/.
# Scale out only after implementing separate work directories per species/AOI.
