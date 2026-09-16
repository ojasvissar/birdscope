#!/usr/bin/env python3
"""Run from the repository root without installing the local package."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fieldwork.pipeline import main

if __name__ == "__main__":
    main()
