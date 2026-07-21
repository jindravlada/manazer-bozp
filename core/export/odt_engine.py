import html
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Mapping
from xml.sax.saxutils import escape as xml_escape


class OdtExportError(Exception):
    """Chyba exportního enginu."""


# Vložení obrázku do textové hodnoty (před escapováním).
# Příklad: "text\\n[[[ODT_IMAGE|/abs/cesta.jpg]]]\\ndalší text"
ODT_IMAGE_MARKER_RE = re.compile(r"\[\[\[ODT_IMAGE\|(.+?)\]\]\]")


class OdtExportEngine:
    """
    Univerzální exportní engine pro ODT šablony.

    Šablona používá placeholdery ve tvaru:
        ${nazev_polozky}

    Hodnoty jsou escapované pro ODT/XML a nové řádky jsou převedené na
    <text:line-break/>. Placeholdery, které nejsou v datech, se ve výstupu
    vyprázdní, aby v dokumentu nezůstávaly technické značky.

    Volitelně lze do textových hodnot vložit značku ``[[[ODT_IMAGE|/cesta]]]``;
    engine ji nahradí vloženým obrázkem v ``Pictures/`` a aktualizuje manifest.
    """

    PLACEHOLDER_RE = re.compile(r"\$\{([A-Za-z0-9_]+)\}")
    _MAX_IMAGE_WIDTH_CM = 12.0
    _MAX_IMAGE_HEIGHT_CM = 9.0

    def render(self, template_path: str | Path, output_path: str | Path, values: Mapping[str, Any]) -> Path:
        template = Path(template_path)
        output = Path(output_path)

        if not template.exists():
            raise FileNotFoundError(f"Šablona nebyla nalezena: {template}")

        if template.suffix.lower() != ".odt":
            raise OdtExportError(f"Šablona musí být ODT soubor: {template}")

        output.parent.mkdir(parents=True, exist_ok=True)

        image_registry: list[tuple[str, Path]] = []
        normalized_values = {
            str(key): self._escape_odt_text(value, image_registry)
            for key, value in dict(values or {}).items()
        }

        try:
            with zipfile.ZipFile(template, "r") as zin, zipfile.ZipFile(output, "w") as zout:
                written_names: set[str] = set()
                for item in zin.infolist():
                    data = zin.read(item.filename)

                    if item.filename in {"content.xml", "styles.xml", "meta.xml"}:
                        xml = data.decode("utf-8")
                        xml = self._replace_placeholders(xml, normalized_values)
                        data = xml.encode("utf-8")
                    elif item.filename == "META-INF/manifest.xml" and image_registry:
                        xml = data.decode("utf-8")
                        xml = self._inject_manifest_images(xml, image_registry)
                        data = xml.encode("utf-8")

                    self._writestr(zout, item, data)
                    written_names.add(item.filename)

                for archive_name, source_path in image_registry:
                    if archive_name in written_names:
                        continue
                    zout.writestr(archive_name, source_path.read_bytes())

        except zipfile.BadZipFile as exc:
            raise OdtExportError(f"Šablona není platný ODT/ZIP soubor: {template}") from exc

        _sync_written_file(output)
        return output.resolve()

    def _replace_placeholders(self, xml: str, values: Mapping[str, str]) -> str:
        def repl(match: re.Match[str]) -> str:
            return values.get(match.group(1), "")

        return self.PLACEHOLDER_RE.sub(repl, xml)

    def _escape_odt_text(self, value: Any, image_registry: list[tuple[str, Path]]) -> str:
        text = "" if value is None else str(value)
        parts: list[str] = []
        last = 0
        for match in ODT_IMAGE_MARKER_RE.finditer(text):
            parts.append(self._escape_plain_text(text[last:match.start()]))
            image_xml = self._image_frame_xml(match.group(1).strip(), image_registry)
            if image_xml:
                parts.append(image_xml)
            last = match.end()
        parts.append(self._escape_plain_text(text[last:]))
        return "".join(parts)

    @staticmethod
    def _escape_plain_text(text: str) -> str:
        escaped = html.escape(text, quote=False)
        return escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<text:line-break/>")

    def _image_frame_xml(self, path_text: str, image_registry: list[tuple[str, Path]]) -> str:
        path = Path(path_text)
        if not path.is_file():
            return ""

        width_cm, height_cm = self._image_display_size_cm(path)
        index = len(image_registry) + 1
        suffix = path.suffix.lower() or ".jpg"
        if suffix not in {".jpg", ".jpeg", ".png", ".gif"}:
            suffix = ".jpg"
        archive_name = f"Pictures/export_img_{index:03d}{suffix}"
        image_registry.append((archive_name, path.resolve()))

        name = f"export_img_{index:03d}"
        href = xml_escape(archive_name, {"\"": "&quot;"})
        return (
            f'<draw:frame draw:name="{name}" text:anchor-type="as-char" '
            f'svg:width="{width_cm:.2f}cm" svg:height="{height_cm:.2f}cm" draw:z-index="0">'
            f'<draw:image xlink:href="{href}" xlink:type="simple" '
            f'xlink:show="embed" xlink:actuate="onLoad"/>'
            f"</draw:frame>"
        )

    def _image_display_size_cm(self, path: Path) -> tuple[float, float]:
        width_px = 1200
        height_px = 900
        try:
            from PIL import Image

            with Image.open(path) as image:
                width_px, height_px = image.size
        except Exception:
            pass

        if width_px <= 0 or height_px <= 0:
            return self._MAX_IMAGE_WIDTH_CM, self._MAX_IMAGE_HEIGHT_CM

        # Assume ~96 DPI for screen photos.
        width_cm = width_px * 2.54 / 96.0
        height_cm = height_px * 2.54 / 96.0
        scale = min(
            self._MAX_IMAGE_WIDTH_CM / width_cm,
            self._MAX_IMAGE_HEIGHT_CM / height_cm,
            1.0,
        )
        return width_cm * scale, height_cm * scale

    @staticmethod
    def _inject_manifest_images(manifest_xml: str, image_registry: list[tuple[str, Path]]) -> str:
        entries: list[str] = []
        if "Pictures/" not in manifest_xml:
            entries.append(
                '<manifest:file-entry manifest:full-path="Pictures/" '
                'manifest:media-type=""/>'
            )
        for archive_name, source_path in image_registry:
            media = _odt_image_media_type(source_path)
            entries.append(
                f'<manifest:file-entry manifest:full-path="{xml_escape(archive_name)}" '
                f'manifest:media-type="{media}"/>'
            )
        if not entries:
            return manifest_xml
        injection = "".join(entries)
        if "</manifest:manifest>" in manifest_xml:
            return manifest_xml.replace("</manifest:manifest>", injection + "</manifest:manifest>")
        return manifest_xml + injection

    @staticmethod
    def _writestr(zout: zipfile.ZipFile, item: zipfile.ZipInfo, data: bytes) -> None:
        new_item = zipfile.ZipInfo(filename=item.filename, date_time=item.date_time)
        new_item.compress_type = item.compress_type
        new_item.comment = item.comment
        new_item.extra = item.extra
        new_item.internal_attr = item.internal_attr
        new_item.external_attr = item.external_attr
        zout.writestr(new_item, data)


def export_odt_template(template_path: str | Path, output_path: str | Path, values: Mapping[str, Any]) -> Path:
    return OdtExportEngine().render(template_path, output_path, values)


def odt_image_marker(path: str | Path) -> str:
    """Vrátí značku pro vložení obrázku do textové hodnoty ODT exportu."""
    return f"[[[ODT_IMAGE|{Path(path)}]]]"


def _odt_image_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".gif":
        return "image/gif"
    return "image/jpeg"


def _sync_written_file(path: Path) -> None:
    if os.name == "nt":
        # Windows – zipfile po close() korektně flushne data.
        # os.fsync() zde není potřeba a může selhat.
        return

    # POSIX/Linux – AppImage může otevřít soubor okamžitě po vytvoření,
    # proto explicitně flushujeme metadata i obsah.
    with path.open("r+b") as handle:
        os.fsync(handle.fileno())
