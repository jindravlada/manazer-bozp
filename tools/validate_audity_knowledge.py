#!/usr/bin/env python3
"""Validace JSON znalostní databáze interních auditů."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from moduly.audity.sluzby.audit_knowledge_validator import (
    default_audity_dir,
    validate_all_catalogs,
)


def main() -> int:
    errors = validate_all_catalogs(default_audity_dir())
    if errors:
        print("Validace znalostní databáze auditu: CHYBA", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("Validace znalostní databáze auditu: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
