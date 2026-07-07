#!/usr/bin/env python3
"""Diagnostický nástroj pro parser právních předpisů."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from moduly.pravni_pozadavky.constants import SECTION_TYPE_LABELS
from moduly.pravni_pozadavky.parser.legal_document_parser import legal_document_parser
from moduly.pravni_pozadavky.parser.legal_document_parser_diagnostics import (
    legal_document_parser_diagnostics,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnostika parseru právních předpisů.")
    parser.add_argument("txt_path", help="Cesta k TXT souboru předpisu.")
    parser.add_argument("--title", required=True, help="Název předpisu.")
    parser.add_argument("--type", required=True, dest="document_type", help="Typ předpisu.")
    parser.add_argument("--number", default="", help="Číslo předpisu.")
    parser.add_argument("--year", type=int, default=None, help="Rok vydání předpisu.")
    parser.add_argument("--export-tree", dest="export_tree", help="Cesta pro export stromu do TXT.")
    parser.add_argument("--export-json", dest="export_json", help="Cesta pro export JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    txt_path = Path(args.txt_path)
    if not txt_path.is_file():
        print(f"Soubor nebyl nalezen: {txt_path}", file=sys.stderr)
        return 1

    try:
        raw_text = txt_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Soubor nelze načíst: {txt_path}", file=sys.stderr)
        raise SystemExit(1) from exc

    parse_result = legal_document_parser.parse_text(
        raw_text,
        document_type=args.document_type,
        number=args.number,
        year=args.year,
        title=args.title,
    )
    diagnostics = legal_document_parser_diagnostics.analyze(parse_result)

    print(f"Počet všech částí: {diagnostics.total_sections}")
    for section_type, count in diagnostics.counts_by_type.items():
        if count:
            label = SECTION_TYPE_LABELS.get(section_type, section_type)
            print(f"  {label}: {count}")
    print(f"Počet chyb hierarchie: {len(diagnostics.errors)}")
    print(f"hierarchy_ok: {'Ano' if diagnostics.hierarchy_ok else 'Ne'}")

    if args.export_tree:
        legal_document_parser_diagnostics.export_tree(parse_result, args.export_tree)
        print(f"Strom exportován do: {args.export_tree}")

    if args.export_json:
        legal_document_parser.export_json(args.export_json, parse_result)
        print(f"JSON exportován do: {args.export_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
