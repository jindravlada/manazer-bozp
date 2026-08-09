"""Chronologický seznam smluv OZO – HTML / PDF výstup."""

from __future__ import annotations

from pathlib import Path

from moduly.smlouvy_ozo.constants import (
    DOCUMENT_LIST_LEGAL,
    DOCUMENT_LIST_TITLE,
    format_date,
)
from moduly.smlouvy_ozo.sluzby.ozo_contract_service import (
    ozo_contract_service,
    relation_date,
)
from moduly.smlouvy_ozo.sluzby.ozo_person_service import ozo_person_service


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class OzoContractListService:
    def missing_ozo_fields(self) -> list[str]:
        return ozo_person_service.missing_for_list_output()

    def build_html(self, year: int) -> str:
        person = ozo_person_service.get_or_empty()
        contracts = ozo_contract_service.list_for_calendar_year(year)
        full_name = ozo_person_service.full_name(person)
        certificate = (person.certificate_number or "").strip()

        rows_html = []
        if not contracts:
            rows_html.append(
                "<tr><td colspan='5'>Pro zvolený rok nejsou evidovány "
                "žádné smluvní vztahy.</td></tr>"
            )
        else:
            for index, contract in enumerate(contracts, start=1):
                rel = relation_date(contract)
                employer = (contract.employer_name or "").strip() or "—"
                ico = (contract.ico or "").strip() or "—"
                number = (contract.contract_number or "").strip() or "—"
                rows_html.append(
                    "<tr>"
                    f"<td>{index}.</td>"
                    f"<td>{_escape(employer)}</td>"
                    f"<td>{_escape(ico)}</td>"
                    f"<td>{_escape(format_date(rel))}</td>"
                    f"<td>{_escape(number)}</td>"
                    "</tr>"
                )

        return f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="utf-8"/>
<title>{_escape(DOCUMENT_LIST_TITLE)} {int(year)}</title>
<style>
  body {{ font-family: sans-serif; font-size: 11pt; color: #111; }}
  h1 {{ font-size: 16pt; margin-bottom: 0.2em; }}
  .meta {{ margin: 0.4em 0 1.2em; }}
  .legal {{ color: #444; font-size: 10pt; margin-bottom: 1em; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #333; padding: 6px 8px; text-align: left; }}
  th {{ background: #f0f0f0; }}
</style>
</head>
<body>
  <h1>{_escape(DOCUMENT_LIST_TITLE)}</h1>
  <div class="legal">{_escape(DOCUMENT_LIST_LEGAL)}</div>
  <div class="meta">
    <div><b>Kalendářní rok:</b> {int(year)}</div>
    <div><b>Odborně způsobilá osoba:</b> {_escape(full_name or "—")}</div>
    <div><b>Číslo osvědčení:</b> {_escape(certificate or "—")}</div>
  </div>
  <table>
    <thead>
      <tr>
        <th>Poř.</th>
        <th>Objednatel</th>
        <th>IČO</th>
        <th>Datum smluvního vztahu</th>
        <th>Číslo smlouvy</th>
      </tr>
    </thead>
    <tbody>
      {"".join(rows_html)}
    </tbody>
  </table>
</body>
</html>
"""

    def write_pdf(self, html: str, path: Path) -> Path:
        from PySide6.QtGui import QTextDocument
        from PySide6.QtPrintSupport import QPrinter

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(path))
        document = QTextDocument()
        document.setHtml(html)
        document.print_(printer)
        return path


ozo_contract_list_service = OzoContractListService()
