#!/usr/bin/env python3
"""
Script to scan subfolders for .txt files and classify them by camera models and films.
Creates a markdown report with folder classifications.
"""

import os
import sys
import argparse
import shutil
import subprocess
import random
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime


CAMERA_PREFIX = 'CAM-'
PROGRAM_PREFIX = 'PN-'
FILM_PREFIX = 'FILM-'
EXIF_UPDATE_MARKER_FILE = 'exif-update.txt'
FILM_STOCK_FILE = 'film_stock.md'

ANONYMIZE_ADJECTIVES = [
    'cool',
    'sunny',
    'beautiful',
    'quiet',
    'vivid',
    'golden',
    'gentle',
    'bright',
]

ANONYMIZE_SUBJECTS = [
    'landscape',
    'building',
    'tree',
    'flower',
    'street',
    'mountain',
    'river',
    'bridge',
]

DATE_FOLDER_PATTERN = re.compile(r'^(\d{6}|\d{8})_(.+)$')


def parse_film_marker_for_table(film_stem):
    """Parse a film marker stem into film, format, color and ISO parts."""
    parts = film_stem.split('-')
    film_iso = None
    film_color = None
    film_format = None

    if parts and parts[-1].isdigit():
        film_iso = int(parts.pop())

    if parts and parts[-1] in {'Color', 'BW', 'IR', 'B/W'}:
        film_color = parts.pop()

    if parts and parts[-1] in {'135', '120'}:
        film_format = parts.pop()

    film_stock = '-'.join(parts) if parts else None
    return {
        'film_stock': film_stock,
        'film_iso': film_iso,
        'film_format': film_format,
        'film_color': film_color,
    }


def normalize_film_color_for_filename(film_color):
    """Normalize stock table color labels to filesystem-safe marker tokens."""
    if film_color == 'B/W':
        return 'BW'
    return film_color


def build_film_marker_filename(film_stock, film_format, film_color, film_iso):
    """Build the FILM marker filename for a stock entry."""
    color_token = normalize_film_color_for_filename(film_color)
    return (
        f"{FILM_PREFIX}{film_stock}-{film_format}-{color_token}-{film_iso}.txt"
    )


def parse_film_stock_table(root_path):
    """Parse film_stock.md into structured stock entries."""
    stock_file = Path(root_path) / FILM_STOCK_FILE
    if not stock_file.exists():
        raise FileNotFoundError(
            f"Film stock file not found: {stock_file}"
        )

    stock_entries = []

    with open(stock_file, 'r', encoding='utf-8') as file_handle:
        for line in file_handle:
            stripped_line = line.strip()
            if not stripped_line.startswith('|'):
                continue

            columns = [column.strip()
                       for column in stripped_line.strip('|').split('|')]
            if len(columns) != 5:
                continue

            if columns[0] in {'Film', '---', '----'}:
                continue

            film_stock, film_iso, film_format, film_color, stock_count = columns
            if not film_stock or not film_iso or not film_format or not film_color:
                continue

            try:
                stock_count_value = int(stock_count)
            except ValueError:
                continue

            stock_entries.append({
                'film_stock': film_stock,
                'film_iso': int(film_iso),
                'film_format': film_format,
                'film_color': film_color,
                'stock_count': stock_count_value,
                'marker_filename': build_film_marker_filename(
                    film_stock,
                    film_format,
                    film_color,
                    int(film_iso),
                ),
            })

    return stock_entries


def analyze_film_stock(root_path, create_missing=False):
    """Check root FILM markers against film_stock.md and optionally create missing files."""
    root_path_obj = Path(root_path)
    stock_entries = parse_film_stock_table(root_path)
    existing_marker_names = {
        path.name
        for path in root_path_obj.glob(f'{FILM_PREFIX}*.txt')
        if path.is_file()
    }

    existing_count = 0
    missing_count = 0
    created_count = 0

    print(f"\nAnalyzing film stock markers from: {FILM_STOCK_FILE}")

    for entry in stock_entries:
        marker_filename = entry['marker_filename']
        marker_path = root_path_obj / marker_filename
        description = (
            f"{entry['film_stock']} {entry['film_format']} {entry['film_color']} "
            f"ISO {entry['film_iso']} (stock: {entry['stock_count']})"
        )

        if marker_filename in existing_marker_names:
            existing_count += 1
            print(f"   EXISTS  {marker_filename} [{description}]")
            continue

        missing_count += 1

        if create_missing:
            marker_path.touch(exist_ok=True)
            existing_marker_names.add(marker_filename)
            created_count += 1
            print(f"   CREATED {marker_filename} [{description}]")
            continue

        print(f"   MISSING {marker_filename} [{description}]")

    print("\n🧾 Film stock marker summary")
    print(f"   Entries checked: {len(stock_entries)}")
    print(f"   Existing markers: {existing_count}")
    print(f"   Missing markers: {missing_count}")
    if create_missing:
        print(f"   Markers created: {created_count}")


def collect_shot_film_rows(root_path):
    """Collect unique film/camera combinations from subfolders for the film table."""
    root_path_obj = Path(root_path)
    shot_rows = defaultdict(set)
    processed_folders = set()

    for txt_file in root_path_obj.rglob('*.txt'):
        folder_path = txt_file.parent

        if folder_path == root_path_obj:
            continue

        try:
            relative_folder_str = str(
                folder_path.relative_to(root_path_obj)).replace('\\', '/')
        except ValueError:
            continue

        if relative_folder_str in processed_folders:
            continue

        processed_folders.add(relative_folder_str)

        metadata = extract_folder_metadata(folder_path)
        if not metadata['camera_model'] or not metadata['film_raw']:
            continue

        key = (
            metadata['film_stock'],
            metadata['film_iso'],
            metadata['film_format'],
            metadata['film_color'],
        )
        shot_rows[key].add(metadata['camera_model'])

    rows = []
    for key in sorted(shot_rows.keys(), key=lambda item: (
        item[0] or '',
        item[1] if item[1] is not None else -1,
        item[2] or '',
        item[3] or '',
    )):
        rows.append({
            'film_stock': key[0],
            'film_iso': key[1],
            'film_format': key[2],
            'film_color': key[3],
            'camera_models': sorted(shot_rows[key]),
        })

    return rows


def generate_film_table_report(shot_rows, output_file='film_iso_shot.md'):
    """Generate the 'Already Shot' markdown table."""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("## Already Shot\n\n")
        f.write("| Film | ISO | Format | Color B/W | Camera |\n")
        f.write("| ---- | --- | ------ | --------- | ------ |\n")

        for row in shot_rows:
            camera_value = ', '.join(row['camera_models'])
            iso_value = '' if row['film_iso'] is None else str(row['film_iso'])
            format_value = row['film_format'] or ''
            color_value = row['film_color'] or ''
            film_value = row['film_stock'] or ''
            f.write(
                f"| {film_value} | {iso_value} | {format_value} | {color_value} | {camera_value} |\n"
            )


def scan_folders_for_txt_files(root_path):
    """
    Recursively scan all subfolders for .txt files and classify them.
    Excludes the root directory itself from scanning.

    Args:
        root_path (str): Root directory to scan

    Returns:
        tuple: (camera_folders, film_folders, camera_films)
            camera_folders: dict mapping camera models to list of folders
            film_folders: dict mapping film types to list of folders
            camera_films: dict mapping camera models to set of used films
    """
    camera_folders = defaultdict(list)
    film_folders = defaultdict(list)
    camera_films = defaultdict(set)
    root_path_obj = Path(root_path)

    # Dictionary to track which folders we've already processed
    processed_folders = set()

    # Recursively find all .txt files
    for txt_file in root_path_obj.rglob('*.txt'):
        # Get the folder containing this .txt file
        folder_path = txt_file.parent

        # Skip files in the root directory itself
        if folder_path == root_path_obj:
            continue

        # Calculate relative path from root
        try:
            relative_folder_path = folder_path.relative_to(root_path_obj)
            # Convert to string with forward slashes for consistency
            relative_folder_str = str(relative_folder_path).replace('\\', '/')
        except ValueError:
            # Skip if we can't calculate relative path
            continue

        # Skip if this folder has already been processed
        if relative_folder_str in processed_folders:
            continue

        # Mark this folder as processed
        processed_folders.add(relative_folder_str)

        # Collect all .txt files in this specific folder (not recursive)
        camera_files = []
        film_files = []

        for txt_file_in_folder in folder_path.glob('*.txt'):
            if txt_file_in_folder.name.startswith(CAMERA_PREFIX):
                camera_files.append(txt_file_in_folder.name)
            elif txt_file_in_folder.name.startswith(PROGRAM_PREFIX):
                continue
            elif txt_file_in_folder.name.startswith(FILM_PREFIX):
                film_files.append(txt_file_in_folder.name)
            elif txt_file_in_folder.name.lower() == EXIF_UPDATE_MARKER_FILE:
                continue
            else:
                continue

        # Classify folder based on content
        if camera_files:
            # Group by camera model (remove .txt extension and 00- prefix)
            for camera_file in camera_files:
                # Remove camera prefix and '.txt' suffix
                camera_model = camera_file[len(CAMERA_PREFIX):-4]
                if relative_folder_str not in camera_folders[camera_model]:
                    camera_folders[camera_model].append(relative_folder_str)

        if film_files:
            # Group by film type (remove .txt extension and film prefix)
            for film_file in film_files:
                film_type = film_file[len(FILM_PREFIX):-4]
                if relative_folder_str not in film_folders[film_type]:
                    film_folders[film_type].append(relative_folder_str)

        # Track which films were used with each camera in this folder.
        if camera_files and film_files:
            camera_models = [
                camera_file[len(CAMERA_PREFIX):-4]
                for camera_file in camera_files
            ]
            film_types = [
                film_file[len(FILM_PREFIX):-4]
                for film_file in film_files
            ]
            for camera_model in camera_models:
                for film_type in film_types:
                    camera_films[camera_model].add(film_type)

    return camera_folders, film_folders, camera_films


def generate_anonymized_folder_map(camera_folders, film_folders):
    """Build a mapping of folder paths to anonymized paths for report publishing."""
    all_folders = set()
    for folders in camera_folders.values():
        all_folders.update(folders)
    for folders in film_folders.values():
        all_folders.update(folders)

    segment_map = {}
    used_anonymized_segments = set()

    def anonymize_segment(segment):
        if segment in segment_map:
            return segment_map[segment]

        match = DATE_FOLDER_PATTERN.match(segment)
        if not match:
            segment_map[segment] = segment
            return segment

        date_part = match.group(1)

        for _ in range(100):
            adjective = random.choice(ANONYMIZE_ADJECTIVES)
            subject = random.choice(ANONYMIZE_SUBJECTS)
            candidate = f"{date_part}_{adjective}_{subject}"
            if candidate not in used_anonymized_segments:
                used_anonymized_segments.add(candidate)
                segment_map[segment] = candidate
                return candidate

        # Fallback to guarantee uniqueness even if random combinations are exhausted.
        suffix = len(used_anonymized_segments) + 1
        fallback = f"{date_part}_anon_{suffix}"
        used_anonymized_segments.add(fallback)
        segment_map[segment] = fallback
        return fallback

    folder_map = {}
    for folder in all_folders:
        parts = folder.split('/')
        anonymized_parts = [anonymize_segment(part) for part in parts]
        folder_map[folder] = '/'.join(anonymized_parts)

    return folder_map


def generate_markdown_report(
    camera_folders,
    film_folders,
    camera_films,
    output_file='photo_classification_report.md',
    anonymize=False,
):
    """
    Generate a markdown report with folder classifications.

    Args:
        camera_folders: dict mapping camera models to list of folders
        film_folders: dict mapping film types to list of folders
        output_file: output filename for the markdown report
    """
    folder_map = generate_anonymized_folder_map(
        camera_folders, film_folders) if anonymize else {}

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Photo Folder Classification Report\n\n")
        f.write(
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        if anonymize:
            f.write("*Folder names are anonymized for publishing.*\n\n")

        # First part: Camera models
        f.write("## 📷 Folders by Camera Model\n\n")

        if camera_folders:
            # Sort camera models alphabetically
            for camera_model in sorted(camera_folders.keys()):
                folders = camera_folders[camera_model]
                f.write(f"### {camera_model}\n")
                f.write(f"*{len(folders)} folder(s)*\n\n")

                for folder in sorted(folders):
                    displayed_folder = folder_map.get(folder, folder)
                    f.write(f"- {displayed_folder}\n")
                f.write("\n")
        else:
            f.write(
                f"*No folders found with camera model files ({CAMERA_PREFIX}*.txt)*\n\n")

        # Second part: Film types
        f.write("## 🎞️ Folders by Film Type\n\n")

        if film_folders:
            # Sort film types alphabetically
            for film_type in sorted(film_folders.keys()):
                folders = film_folders[film_type]
                f.write(f"### {film_type}\n")
                f.write(f"*{len(folders)} folder(s)*\n\n")

                for folder in sorted(folders):
                    displayed_folder = folder_map.get(folder, folder)
                    f.write(f"- {displayed_folder}\n")
                f.write("\n")
        else:
            f.write(
                f"*No folders found with film type files ({FILM_PREFIX}*.txt)*\n\n")

        # Third part: Films used by camera
        f.write("## 📷🎞️ Films Used by Camera\n\n")

        if camera_films:
            for camera_model in sorted(camera_films.keys()):
                films = sorted(camera_films[camera_model])
                f.write(f"### {camera_model}\n")
                f.write(f"*{len(films)} film(s)*\n\n")
                for film in films:
                    f.write(f"- {film}\n")
                f.write("\n")
        else:
            f.write("*No camera/film combinations found.*\n\n")

        # Summary
        f.write("## 📊 Summary\n\n")
        f.write(f"- **Camera models found:** {len(camera_folders)}\n")
        f.write(f"- **Film types found:** {len(film_folders)}\n")

        total_camera_folders = sum(len(folders)
                                   for folders in camera_folders.values())
        total_film_folders = sum(len(folders)
                                 for folders in film_folders.values())

        f.write(
            f"- **Total folders with camera data:** {total_camera_folders}\n")
        f.write(f"- **Total folders with film data:** {total_film_folders}\n")


def print_summary(camera_folders, film_folders):
    """Print a summary to console."""
    print(f"\n📷 Camera Models Found: {len(camera_folders)}")
    for camera_model in sorted(camera_folders.keys()):
        print(
            f"   {camera_model}: {len(camera_folders[camera_model])} folder(s)")

    print(f"\n🎞️ Film Types Found: {len(film_folders)}")
    for film_type in sorted(film_folders.keys()):
        print(f"   {film_type}: {len(film_folders[film_type])} folder(s)")


def extract_folder_metadata(folder_path):
    """Extract camera, film stock, ISO and program info from marker .txt files."""
    camera_model = None
    film_stock = None
    film_iso = None
    film_format = None
    film_color = None
    film_raw = None
    program_name = None

    txt_files = sorted(folder_path.glob('*.txt'))

    for txt_file in txt_files:
        name = txt_file.name
        stem = txt_file.stem

        if name.lower() == EXIF_UPDATE_MARKER_FILE:
            continue

        if name.startswith(CAMERA_PREFIX):
            camera_model = stem[len(CAMERA_PREFIX):]
            continue

        if name.startswith(PROGRAM_PREFIX):
            program_name = stem[len(PROGRAM_PREFIX):]
            continue

        if not name.startswith(FILM_PREFIX):
            continue

        # Files with the film prefix are treated as film information.
        # Supports legacy markers (FILM-Name-ISO), format-aware markers
        # (FILM-Name-Format-ISO), and color-tagged markers
        # (FILM-Name-Format-ColorOrBW-ISO). Only the film name is kept as
        # film_stock for EXIF keywords.
        film_stem = stem[len(FILM_PREFIX):]
        film_raw = film_stem
        parsed_film = parse_film_marker_for_table(film_stem)
        film_stock = parsed_film['film_stock']
        film_iso = parsed_film['film_iso']
        film_format = parsed_film['film_format']
        film_color = parsed_film['film_color']

    return {
        'camera_model': camera_model,
        'film_stock': film_stock,
        'film_iso': film_iso,
        'film_format': film_format,
        'film_color': film_color,
        'film_raw': film_raw,
        'program_name': program_name,
    }


def update_photos_exif_data(root_path):
    """Recursively update image metadata from marker files using exiftool."""
    exiftool_path = shutil.which('exiftool')
    if not exiftool_path:
        print("\n⚠️ --exif-update requested, but 'exiftool' was not found in PATH.")
        print("   Install ExifTool and re-run to enable metadata updates.")
        return

    image_extensions = {'.jpg', '.jpeg', '.tif', '.tiff', '.png', '.webp'}
    folders_updated = 0
    folders_ignored = 0
    pictures_updated = 0
    pictures_ignored = 0

    for current_root, _, files in os.walk(root_path):
        folder_path = Path(current_root)
        marker_path = folder_path / EXIF_UPDATE_MARKER_FILE

        folder_image_files = [
            folder_path / file_name
            for file_name in files
            if (folder_path / file_name).suffix.lower() in image_extensions
        ]

        if marker_path.exists():
            folders_ignored += 1
            pictures_ignored += len(folder_image_files)
            continue

        metadata = extract_folder_metadata(folder_path)

        has_metadata = any(
            value is not None for value in (
                metadata['camera_model'],
                metadata['film_stock'],
                metadata['film_iso'],
                metadata['program_name'],
            )
        )

        if not has_metadata:
            folders_ignored += 1
            pictures_ignored += len(folder_image_files)
            continue

        image_files = [str(file_path) for file_path in folder_image_files]

        if not image_files:
            folders_ignored += 1
            continue

        cmd = [exiftool_path, '-overwrite_original']

        if metadata['camera_model']:
            cmd.append(f"-Model={metadata['camera_model']}")

        if metadata['film_iso'] is not None:
            cmd.append(f"-ISO={metadata['film_iso']}")

        if metadata['program_name']:
            cmd.append(f"-Software={metadata['program_name']}")
            cmd.append(f"-XMP-xmp:CreatorTool={metadata['program_name']}")

        if metadata['film_stock']:
            cmd.append(f"-XMP-dc:Subject+={metadata['film_stock']}")
            cmd.append(f"-IPTC:Keywords+={metadata['film_stock']}")

        cmd.extend(image_files)

        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"\n⚠️ Failed metadata update in folder: {folder_path}")
            stderr = (result.stderr or '').strip()
            if stderr:
                print(f"   {stderr}")
            folders_ignored += 1
            pictures_ignored += len(image_files)
            continue

        marker_path.touch(exist_ok=True)
        folders_updated += 1
        pictures_updated += len(image_files)

    print("\n📝 EXIF update summary")
    print(f"   Folders updated: {folders_updated}")
    print(f"   Folders ignored: {folders_ignored}")
    print(f"   Pictures updated: {pictures_updated}")
    print(f"   Pictures ignored: {pictures_ignored}")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Scan subfolders for camera/film marker files and generate a markdown report. "
            "Optionally update image metadata using marker files."
        )
    )
    parser.add_argument(
        'root_path',
        nargs='?',
        default='.',
        help='Root directory to scan (default: current directory)'
    )
    parser.add_argument(
        '--exif-update',
        action='store_true',
        help='Recursively update image metadata from marker files (requires exiftool)'
    )
    parser.add_argument(
        '--anonymize',
        action='store_true',
        help='Anonymize dated folder names in the generated markdown report'
    )
    parser.add_argument(
        '--film-table',
        action='store_true',
        help='Generate a film_iso_shot.md table of films already shot'
    )
    parser.add_argument(
        '--film-stock-analyze',
        action='store_true',
        help='Check root FILM markers against film_stock.md and log existing/missing files'
    )
    parser.add_argument(
        '--film-stock-create',
        action='store_true',
        help='Check root FILM markers against film_stock.md and create missing files'
    )
    return parser.parse_args()


def main():
    """Main function to run the script."""
    args = parse_args()
    root_path = args.root_path
    generate_standard_report = not (
        args.exif_update
        or args.film_table
        or args.film_stock_analyze
        or args.film_stock_create
    )

    print(f"Scanning subfolders in: {os.path.abspath(root_path)}")
    print("(Note: Files in the root directory itself are excluded from scanning)")

    # Check if root path exists
    if not os.path.exists(root_path):
        print(f"Error: Path '{root_path}' does not exist.")
        sys.exit(1)

    if args.exif_update:
        print("\nUpdating photo metadata recursively (--exif-update enabled)...")
        update_photos_exif_data(root_path)

        if not (args.film_table or args.film_stock_analyze or args.film_stock_create):
            return

    if args.film_stock_analyze or args.film_stock_create:
        analyze_film_stock(root_path, create_missing=args.film_stock_create)
        if not (args.film_table or generate_standard_report):
            return

    # Scan for .txt files and classify folders (excluding root directory)
    print("Recursively scanning subfolders for .txt files...")
    camera_folders, film_folders, camera_films = scan_folders_for_txt_files(
        root_path)

    if args.film_table:
        shot_rows = collect_shot_film_rows(root_path)
        film_table_output = 'film_iso_shot.md'
        print(f"\nGenerating film table: {film_table_output}")
        generate_film_table_report(shot_rows, film_table_output)
        print(
            f"✅ Film table generated successfully: {os.path.abspath(film_table_output)}")

        if not generate_standard_report:
            return

    # Print summary to console
    print_summary(camera_folders, film_folders)

    # Generate markdown report
    output_file = (
        'photo_classification_report_anonymized.md'
        if args.anonymize
        else 'photo_classification_report.md'
    )
    print(f"\nGenerating markdown report: {output_file}")
    generate_markdown_report(
        camera_folders,
        film_folders,
        camera_films,
        output_file,
        anonymize=args.anonymize,
    )

    print(f"✅ Report generated successfully: {os.path.abspath(output_file)}")


if __name__ == "__main__":
    main()
