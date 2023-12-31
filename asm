#!/bin/bash

# Get the directory where the script is actually located
SCRIPT_DIR=$(dirname "$(realpath "$0")")

# Execute p1.py using the path relative to the script's location
python "$SCRIPT_DIR/asm_impls/p1.py" "$@"
