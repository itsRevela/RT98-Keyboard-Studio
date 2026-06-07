#!/usr/bin/env python3
"""Convenience launcher: `python run.py` (equivalent to `python -m app.main`)."""
from app.main import main

if __name__ == "__main__":
    raise SystemExit(main())
