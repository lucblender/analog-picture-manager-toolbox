#!/usr/bin/env python3
"""
Recursively rename files by prefix.

Supports two modes:
1) Replace OLD_PREFIX with NEW_PREFIX.
2) Optionally rename files that do not start with any known prefix
   and match configured patterns (useful for film .txt files).
"""

import os
from pathlib import Path


# Main prefix replacement config (requested as global vars)
OLD_PREFIX = 'FILM-Kodak-Ultramax-'
NEW_PREFIX = 'FILM-Kodak-Ultramax-135-'

# Optional extra mode: rename files with no known prefix
ENABLE_NO_PREFIX_MODE = False
NO_PREFIX_OLD_PREFIX = ''
NO_PREFIX_NEW_PREFIX = 'FILM-'
NO_PREFIX_GLOB_PATTERNS = ['*.txt']

# Prefixes considered as "already prefixed" when NO_PREFIX mode is enabled
KNOWN_PREFIXES = ['CAM-', 'PN-', 'FILM-']

# Filenames to never rename
IGNORED_FILENAMES = {'exif-update.txt'}

# Set to True to preview without renaming
DRY_RUN = False


def should_rename_no_prefix_file(file_path):
    """Return True if file matches no-prefix rename criteria."""
    file_name = file_path.name

    if file_name in IGNORED_FILENAMES:
        return False

    if any(file_name.startswith(prefix) for prefix in KNOWN_PREFIXES):
        return False

    return any(file_path.match(pattern) for pattern in NO_PREFIX_GLOB_PATTERNS)


def build_new_name(file_name):
    """Return new name for a file, or None if no rename is needed."""
    if file_name in IGNORED_FILENAMES:
        return None

    if OLD_PREFIX and file_name.startswith(OLD_PREFIX):
        return NEW_PREFIX + file_name[len(OLD_PREFIX):]

    if ENABLE_NO_PREFIX_MODE:
        if NO_PREFIX_OLD_PREFIX and file_name.startswith(NO_PREFIX_OLD_PREFIX):
            return NO_PREFIX_NEW_PREFIX + file_name[len(NO_PREFIX_OLD_PREFIX):]

    return None


def rename_files_recursively(root_path):
    """Rename matching files recursively under root_path."""
    root = Path(root_path)
    if not root.exists():
        print(f"Error: Path does not exist: {root}")
        return

    renamed_count = 0
    ignored_count = 0

    for current_root, _, files in os.walk(root):
        current_folder = Path(current_root)

        for file_name in files:
            source_path = current_folder / file_name
            new_name = build_new_name(file_name)

            if new_name is None and ENABLE_NO_PREFIX_MODE and should_rename_no_prefix_file(source_path):
                new_name = NO_PREFIX_NEW_PREFIX + file_name

            if new_name is None or new_name == file_name:
                ignored_count += 1
                continue

            target_path = current_folder / new_name

            if target_path.exists():
                print(f"SKIP (target exists): {source_path} -> {target_path}")
                ignored_count += 1
                continue

            print(f"RENAME: {source_path} -> {target_path}")
            if not DRY_RUN:
                source_path.rename(target_path)

            renamed_count += 1

    print("\nRename summary")
    print(f"  Renamed: {renamed_count}")
    print(f"  Ignored: {ignored_count}")
    if DRY_RUN:
        print("  Mode: DRY_RUN=True (no file was actually renamed)")


if __name__ == '__main__':
    rename_files_recursively('.')
