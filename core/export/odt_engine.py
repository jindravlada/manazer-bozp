import html
import re
import zipfile
from pathlib import Path
from typing import Any, Mapping


class OdtExportError(Exception):
    """Chyba exportního enginu."""


class OdtExportEngine:
    """
    Univerzální exportní engine pro ODT šablony.

    Šablona používá placeholdery ve tvaru:
        ${nazev_polozky}

    Hodnoty jsou escapované pro ODT/XML a nové řádky jsou převedené na
    <text:line-break/>. Placeholdery, které nejsou v datech, se ve výstupu
    vyprázdní, aby v dokumentu nezůstávaly technické značky.
    """

    PLACEHOLDER_RE = re.compile(r"\$\{([A-Za-z0-9_]+)\}")

    def render(self, template_path: str | Path, output_path: str | Path, values: Mapping[str, Any]) -> Path:
        template = Path(template_path)
        output = Path(output_path)

        if not template.exists():
            raise FileNotFoundError(f"Šablona nebyla nalezena: {template}")

        if template.suffix.lower() != ".odt":
            raise OdtExportError(f"Šablona musí být ODT soubor: {template}")

        output.parent.mkdir(parents=True, exist_ok=True)

        normalized_values = {str(key): self._escape_odt_text(value) for key, value in dict(values or {}).items()}

        try:
            with zipfile.ZipFile(template, "r") as zin, zipfile.ZipFile(output, "w") as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)

                    if item.filename in {"content.xml", "styles.xml", "meta.xml"}:
                        xml = data.decode("utf-8")
                        xml = self._replace_placeholders(xml, normalized_values)
                        data = xml.encode("utf-8")

                    new_item = zipfile.ZipInfo(filename=item.filename, date_time=item.date_time)
                    new_item.compress_type = item.compress_type
                    new_item.comment = item.comment
                    new_item.extra = item.extra
                    new_item.internal_attr = item.internal_attr
                    new_item.external_attr = item.external_attr
                    zout.writestr(new_item, data)

        except zipfile.BadZipFile as exc:
            raise OdtExportError(f"Šablona není platný ODT/ZIP soubor: {template}") from exc

        return output

    def _replace_placeholders(self, xml: str, values: Mapping[str, str]) -> str:
        def repl(match: re.Match[str]) -> str:
            return values.get(match.group(1), "")

        return self.PLACEHOLDER_RE.sub(repl, xml)

    def _escape_odt_text(self, value: Any) -> str:
        text = "" if value is None else str(value)
        escaped = html.escape(text, quote=False)
        return escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<text:line-break/>")


def export_odt_template(template_path: str | Path, output_path: str | Path, values: Mapping[str, Any]) -> Path:
    return OdtExportEngine().render(template_path, output_path, values)
