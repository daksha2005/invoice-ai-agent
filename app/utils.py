import os

def ensure_dir_exists(filepath: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
