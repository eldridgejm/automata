#!/bin/sh
# Build practice problems into the website content directory.
# In a real project, this might run a Jupyter notebook, compile LaTeX,
# or process source files through a custom pipeline.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$SCRIPT_DIR/src"
DEST_DIR="$SCRIPT_DIR/../website/content/practice"

mkdir -p "$DEST_DIR"

for src in "$SRC_DIR"/*.md; do
    cp "$src" "$DEST_DIR/"
done
