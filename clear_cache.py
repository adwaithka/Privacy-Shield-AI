"""
Run this once after updating any .py file to clear Python's bytecode cache:
    python clear_cache.py
Then restart uvicorn:
    uvicorn app:app --reload
"""
import shutil, os, pathlib

backend_dir = pathlib.Path(__file__).parent
cache_dir = backend_dir / "__pycache__"
if cache_dir.exists():
    shutil.rmtree(cache_dir)
    print(f"Deleted {cache_dir}")
else:
    print("No __pycache__ found")

print("Now restart uvicorn: uvicorn app:app --reload")