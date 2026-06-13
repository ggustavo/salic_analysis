import json
import os
import re

def sanitize_name(name):
    """Sanitizes segment names for folder usage (removes special chars, replaces spaces)."""
    # Remove any non-alphanumeric, non-space, non-dash characters
    name = re.sub(r'[^\w\s-]', '', name).strip()
    # Replace spaces with underscores
    return name.replace(' ', '_')


def save_json(data, file_path):
    """Utility to save data as JSON."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_json(file_path, default=None):
    """Utility to load data from JSON file."""
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default if default is not None else {}
