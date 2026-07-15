"""Make the v1.2 package importable under pytest (adds this dir to sys.path)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
