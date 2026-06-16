# Analog Picture Manager Toolbox

This repo contains a few scripts I developed (with help of copilot) to help me manage my analog picture scans. With the tools you can:

- Create resume
- modify EXIF
- manage your film list ...

## TOC

- [Analog Picture Manager Toolbox](#analog-picture-manager-toolbox)
  - [TOC](#toc)
  - [analog-picture-manager](#analog-picture-manager)
    - [Metadata files](#metadata-files)
    - [Script use](#script-use)
      - [Default](#default)
        - [Anonymize](#anonymize)
      - [Exif Update](#exif-update)
      - [Film management](#film-management)
        - [Film table](#film-table)
        - [Film stock](#film-stock)
      - [rename-prefix-recursive](#rename-prefix-recursive)
        - [Main idea](#main-idea)
        - [Prefix to prefix rename](#prefix-to-prefix-rename)
        - [No-prefix mode](#no-prefix-mode)
        - [Safety](#safety)

## analog-picture-manager

The analog picture manager will scan a path and its subfolders recursively to help you classify/manage and change EXIF of your analog picture scans.

By default, it will analyze subfolders for specific txt files whose names represent metadata for the content of a subfolder. This is a simple technique that is visible and requires no technical knowledge, just simple txt files with names that represent film, camera, and scanner.

**INITIAL SUBFOLDER NAMES SHOULD FOLLOW THE FORM: YYYYMM_foldername or YYYYMMDD_foldername structure, e.g. 20260616_MySuperPhotoSession.**

### Metadata files

Three types of metadata files exist.

- camera: CAM-nameOfYourCamera.txt
  - nameOfYourCamera : the name of your camera
    - eg: CAM-AgfaBillyRecord.txt
- FILM: FILM-BrandOfYourFilm-NameOfYourFilm-Format-ColorBW-ISO.txt
  - BrandOfYourFilm : the film brand
  - NameOfYourFilm : the name of your film
  - Format : Your film format -> 135 or 120
  - ColorBW : Type of film, color, black and white, IR -> Color, BW, IR
  - ISO : Film sensitivity
    - eg: FILM-Kodak-Ektar-135-Color-100.txt
- Program name to scan your negative, used for EXIF: PN-programName.txt
  - programName : your scan program name
    - eg: PN-Epson-Scan.txt

In each subfolder containing scans for a film, you can put one metadata file for each category.

### Script use

```
python analog-picture-manager.py --help

Scan subfolders for camera/film marker files and generate a markdown report. Optionally
update image metadata using marker files.

positional arguments:
  root_path             Root directory to scan (default: current directory)

options:
  -h, --help            show this help message and exit
  --exif-update         Recursively update image metadata from marker files (requires
                        exiftool)
  --anonymize           Anonymize dated folder names in the generated markdown report
  --film-table          Generate a film_iso_shot.md table of films already shot
  --film-stock-analyze  Check root FILM markers against film_stock.md and log
                        existing/missing files
  --film-stock-create   Check root FILM markers against film_stock.md and create
                        missing files
```

#### Default

By default analog-picture-manager.py scans subfolders for camera/film marker files and generates a markdown report named photo_classification_report.md.

The report contains four sections:

- Folders by Camera Model
  - Tells you which picture subfolders were made using a CAM
- Folders by Film Type
  - Tells you which picture subfolders were made using a FILM
- Films Used by Camera
  - Tells you which FILM was used with a CAM
- Summary
  - Camera models found
  - Film types found
  - Total folders with camera data
  - Total folders with film data

Example:

```markdown
# Photo Folder Classification Report

Generated on: 2026-06-15 20:25:33

## 📷 Folders by Camera Model

### AgfaBillyRecord
*2 folder(s)*

- Folder1
- Folder2

### ...

## 📷🎞️ Films Used by Camera

### AgfaBillyRecord
*2 film(s)*

- Illford-XP2-120-BW-400
- Kodak-Porta-120-Color-400

### ...

## 📊 Summary

- **Camera models found:** 4
- **Film types found:** 11
- **Total folders with camera data:** 27
- **Total folders with film data:** 27
```

##### Anonymize

By using `--anonymize`, it will generate a report named photo_classification_report_anonymized.md where folder names are anonymized. It will take the initial folder name `YYYYMM_foldername` or `YYYYMMDD_foldername` and create a new anonymized folder name while keeping the date: `YYYYMM_anonymizedFoldername` or `YYYYMMDD_anonymizedFoldername`. This can be used if you want to share your report online but your folder names hold some secrets.

e.g.:

- 202308_gentle_landscape
- 202308_bright_flower
- 202312_cool_building
- 202402_sunny_tree

#### Exif Update

By using `--exif-update`, the script will go recursively in subfolders and modify the EXIF of your scans according to your metadata txt files.

This part of the script requires exif-tool on your computer and in your PATH. Download it on the [official exif-tool page](https://exiftool.org/).

- CAM-xxxx.txt -> camera model -> EXIF Model
- FILM-xxxx.txt -> film file, film stock and ISO parsed by separating the filename with '-'
  - ISO -> EXIF ISO
  - Film stock -> XMP Subject + IPTC Keywords
- PN-xxxx.txt -> program name -> EXIF Software + XMP CreatorTool

When a folder has been scanned and EXIF has been modified for all its content, it will create a metadata file named *exif-update.txt* that tells the script not to redo EXIF update in this subfolder.

#### Film management

##### Film table

By using `--film-table`, the script generates a markdown file named *film_iso_shot.md* from your `FILM-*.txt` files.

This table is useful to quickly see what film you already used.

Example:

```markdown
## Already Shot

| Film | ISO | Format | Color B/W | Camera |
| ---- | --- | ------ | --------- | ------ |
| Fujifilm-FujiColor | 200 | 135 | Color | AgfaOptima200 |
| Illford-FP4Plus | 125 | 135 | BW | AgfaOptima200, ZeissIkonContessa |
| Illford-HP5Plus | 400 | 120 | BW | Kiev88 |
```

The parser is based on your FILM file naming. Preferred format:

- `FILM-Brand-Name-Format-ColorBW-ISO.txt`
  - Legacy and shorter variants are also supported (for example without format and/or color)
  - Film column is generated from Brand + Name (+ optional details)
  - ISO column is generated from the last numeric part
  - Format column is parsed from the filename when present
  - Color B/W is generated from ColorBW part
  - Camera is generated by parsing subfolders and finding where a FILM file is paired with a CAM file

##### Film stock

Film stock management uses a file named *film_stock.md* in the root folder.

With this feature you can compare:

- What FILM you already shot (detected with root `FILM-*.txt` markers)
- What FILM you still have in stock (declared in *film_stock.md*)
- Create missing FILM metadata files with the correct naming format for future uses

Two options are available:

- `--film-stock-analyze`
  - Check root FILM markers against *film_stock.md*
  - Log existing/missing files
- `--film-stock-create`
  - Same check as analyze
  - Create missing entries/files according to script behavior

This part helps you keep your film inventory synced with your real usage.

#### rename-prefix-recursive

This second script helps you rename marker files recursively when your naming convention changes, or if you want to rename a specific file.

Example use case:

- Prefix:
  - old camera prefix was `00-`
  - new camera prefix is `CAM-`
- Metadata file naming error, e.g. correcting FILM `FILM-Kokak-Porta-160.txt` to `FILM-Kodak-Porta-160.txt`
  - set old prefix to `FILM-Kokak`
  - set new prefix to `FILM-Kodak`

The script can batch rename all matching files in all subfolders.

##### Main idea

It uses global vars at the top of the script so you can configure quickly:

- old prefix
- new prefix
- known prefixes
- optional no-prefix mode
- dry-run mode

##### Prefix to prefix rename

Typical example:

- `00-AgfaBillyRecord.txt` -> `CAM-AgfaBillyRecord.txt`

##### No-prefix mode

You can also target files that do not start with known prefixes.

This is useful for film files migration, for example when you had film files without prefix and want to move to `FILM-` naming.

Example:

- `Kodak-Porta-160.txt` -> `FILM-Kodak-Porta-160.txt`

##### Safety

- Use DRY_RUN first to preview rename operations
- Existing target file is skipped to avoid overwrite
