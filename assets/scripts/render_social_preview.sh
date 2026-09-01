#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE="$ROOT_DIR/assets/social-preview.svg"
PROFILE="$ROOT_DIR/assets/profile.png"
OUTPUT="$ROOT_DIR/assets/social-preview.png"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

rsvg-convert --format=png --output="$TEMP_DIR/card.png" "$SOURCE"
convert "$PROFILE" -resize '64x64!' -alpha on \
  \( -size 64x64 xc:none -fill white -draw 'circle 32,32 32,2' \) \
  -compose CopyOpacity -composite "$TEMP_DIR/profile.png"
convert "$TEMP_DIR/card.png" "$TEMP_DIR/profile.png" -geometry +74+60 -compose over -composite \
  -strip -set date:timestamp '1970-01-01T00:00:00+00:00' \
  -define png:exclude-chunk=date,time "$OUTPUT"
