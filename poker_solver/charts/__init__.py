"""Data-only package for precomputed solver charts.

Files in this package (e.g. `pushfold_v1.json`) are loaded by sibling modules
via `importlib.resources`; this `__init__.py` exists so the directory is a
proper package and the JSON ships inside the installed wheel.
"""
