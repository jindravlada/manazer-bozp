#!/usr/bin/env bash
# Spouštěč zálohy zdrojového projektu.
# Vlastní zálohování zůstává v tools/backup_source.py.
set -euo pipefail

source="${BASH_SOURCE[0]}"
while [ -L "$source" ]; do
  dir="$(cd "$(dirname "$source")" && pwd -P)"
  link="$(readlink "$source")"
  if [[ "$link" != /* ]]; then
    source="$dir/$link"
  else
    source="$link"
  fi
done

root="$(cd "$(dirname "$source")" && pwd -P)"
cd "$root"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Nelze spustit zálohu zdrojového projektu: v systému není dostupný python3." >&2
  exit 127
fi

set +e
python3 tools/backup_source.py
status=$?
set -e

if [ "$status" -ne 0 ]; then
  echo "Zálohu zdrojového projektu se nepodařilo dokončit." >&2
fi
exit "$status"
