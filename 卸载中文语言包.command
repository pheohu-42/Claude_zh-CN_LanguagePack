#!/bin/bash
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_PATH="$SCRIPT_DIR/LanguagePack.mac.py"
PYTHON_BIN="/usr/bin/python3"

if [ ! -f "$SCRIPT_PATH" ]; then
  echo "Internal uninstaller script not found: $SCRIPT_PATH"
  read -r -p "Press Enter to close..."
  exit 1
fi

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi

if [ -z "${PYTHON_BIN:-}" ]; then
  echo "python3 not found. Please install or enable the system Python 3 runtime."
  read -r -p "Press Enter to close..."
  exit 1
fi

cd "$SCRIPT_DIR" || exit 1
sudo "$PYTHON_BIN" "$SCRIPT_PATH" --uninstall --user-home "$HOME" --launch
STATUS=$?
if [ $STATUS -ne 0 ]; then
  echo
  echo "Uninstaller script failed."
fi
read -r -p "Press Enter to close..."
exit $STATUS
