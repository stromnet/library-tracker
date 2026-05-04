#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="$ROOT_DIR/dist"
GIT_REV="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo nogit)"
if git -C "$ROOT_DIR" diff --quiet --ignore-submodules HEAD 2>/dev/null; then
  DIRTY_SUFFIX=""
else
  DIRTY_SUFFIX="-dirty"
fi

if git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  EXACT_TAG="$(git -C "$ROOT_DIR" tag --points-at HEAD | head -n 1)"
  if [[ -n "$EXACT_TAG" ]]; then
    VERSION_PART="$EXACT_TAG-$GIT_REV"
  else
    PREV_TAG="$(git -C "$ROOT_DIR" describe --tags --abbrev=0 2>/dev/null || echo untagged)"
    if [[ "$PREV_TAG" == "untagged" ]]; then
      CHANGE_COUNT="$(git -C "$ROOT_DIR" rev-list --count HEAD 2>/dev/null || echo 0)"
    else
      CHANGE_COUNT="$(git -C "$ROOT_DIR" rev-list --count "$PREV_TAG"..HEAD 2>/dev/null || echo 0)"
    fi
    VERSION_PART="$PREV_TAG-$CHANGE_COUNT-$GIT_REV"
  fi
else
  VERSION_PART="nogit-$GIT_REV"
fi

PKG_DIR="$DIST_DIR/library-tracker"
ZIP_PATH="$DIST_DIR/library-tracker-$VERSION_PART$DIRTY_SUFFIX.zip"

rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR"
mkdir -p "$DIST_DIR"

copy_paths=(
  library_tracker
  config
  README.md
  pyproject.toml
  requirements.txt
  run.bat
  run.ps1
  setup.bat
)

for path in "${copy_paths[@]}"; do
  cp -R "$ROOT_DIR/$path" "$PKG_DIR/"
done

find "$PKG_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$PKG_DIR" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

(
  cd "$DIST_DIR"
  zip -r "$(basename "$ZIP_PATH")" "$(basename "$PKG_DIR")" >/dev/null
)

echo "Built: $ZIP_PATH"
