#!/usr/bin/env bash
set -euo pipefail

dir="${1:-}"

if [[ -z "$dir" ]]; then
  echo "Usage: $0 /path/to/image-directory" >&2
  exit 1
fi

if [[ ! -d "$dir" ]]; then
  echo "Error: '$dir' is not a directory" >&2
  exit 1
fi

command -v exiftool >/dev/null 2>&1 || {
  echo "Error: exiftool is not installed" >&2
  exit 1
}

find "$dir" -type f \( \
  -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o \
  -iname '*.tif' -o -iname '*.tiff' -o -iname '*.webp' -o \
  -iname '*.heic' -o -iname '*.heif' -o -iname '*.gif' \
\) -print0 |
while IFS= read -r -d '' file; do
  exiftool -all= -overwrite_original "$file" >/dev/null
done