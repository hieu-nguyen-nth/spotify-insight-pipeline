#!/usr/bin/env python3
"""Local entry point. Importing or invoking help never performs model calls."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from spotify_pipeline.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

