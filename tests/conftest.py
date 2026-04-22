"""Shared pytest fixtures."""
import os
import sys
from pathlib import Path

# Make the project root importable as a package
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
