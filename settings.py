"""settings.py - tiny, validated settings file (only known keys, only booleans)."""
import json
import os

DEFAULTS = {"capitalize": True, "fix_words": True}
MAX_BYTES = 4096


def load(path):
    settings = dict(DEFAULTS)
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return settings
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return settings
    if isinstance(data, dict):
        for key in DEFAULTS:
            if isinstance(data.get(key), bool):
                settings[key] = data[key]
    return settings


def save(path, settings):
    tmp = path + ".tmp"
    clean = {key: bool(settings.get(key, default)) for key, default in DEFAULTS.items()}
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)
    os.replace(tmp, path)          # atomic: never leaves a half-written file