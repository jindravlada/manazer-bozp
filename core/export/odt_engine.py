import html
import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence
from xml.sax.saxutils import escape as xml_escape


class OdtExportError(Exception):
    """Chyba exportního enginu."""


# Vložení obrázku do textové hodnoty (před escapováním).
# Příklad: "text\\n[[[ODT_IMAGE|/abs/cesta.jpg]]]\\ndalší text"
ODT_IMAGE_MARKER_RE = re.compile(r"\[\[\[ODT_IMAGE\|(.+?)\]\]\]")

# Placeholdér uvnitř běžného (ne self-closing) odstavce.
# Self-closing <text:p ... /> nesmí být brán jako otevírací tag – jinak by
# následující odstavec s placeholdérem byl chybně spárován a vznikly by
# vnořené <text:p> (neplatné ODF).
_PLACEHOLDER_PARA_RE = re.compile(
    r"<text:p(?![^>]*/>)(?P<attrs>[^>]*)>"
    r"(?P<before>(?:(?!</text:p>).)*?)"
    r"\$\{(?P<key>[A-Za-z0-9_]+)\}"
    r"(?P<after>(?:(?!</text:p>).)*?)"
    r"</text:p>",
    re.DOTALL,
)

_ODT_FRAGMENT_PREFIX = "[[[ODT_FRAGMENT]]]"

_EXPORT_IMAGE_STYLE = "ExportImage"
_AUDIT_NOTE_STYLE = "AuditNote"
_AUDIT_BOLD_STYLE = "AuditBold"
_AUDIT_CRITERION_STYLE = "AuditCriterion"


@dataclass(frozen=True)
class OdtTextRun:
    """Úsek textu uvnitř odstavce (volitelně tučně)."""

    text: str
    bold: bool = False


@dataclass
class OdtParagraph:
    """Jeden ODT odstavec – text, poznámka, nebo samostatná fotografie."""

    style: str = "Standard"
    runs: list[OdtTextRun] = field(default_factory=list)
    image_path: Path | None = None
    blank: bool = False

    @classmethod
    def text(
        cls,
        value: str,
        *,
        style: str = "Standard",
        bold: bool = False,
    ) -> "OdtParagraph":
        return cls(style=style, runs=[OdtTextRun(value, bold=bold)])

    @classmethod
    def blank_line(cls, *, style: str = "Standard") -> "OdtParagraph":
        return cls(style=style, blank=True)

    @classmethod
    def image(cls, path: str | Path, *, style: str = "Standard") -> "OdtParagraph":
        return cls(style=style, image_path=Path(path))

    @classmethod
    def bullet_bold_name(cls, name: str, *, bullet: str = "• ") -> "OdtParagraph":
        return cls(
            style="Standard",
            runs=[OdtTextRun(bullet, bold=False), OdtTextRun(name, bold=True)],
        )

    @classmethod
    def note(
        cls,
        body: str,
        *,
        label: str = "Poznámka auditora:",
    ) -> list["OdtParagraph"]:
        """Poznámka / komentář jako samostatné odstavce se stylem AuditNote."""
        paragraphs = [
            cls(
                style=_AUDIT_NOTE_STYLE,
                runs=[OdtTextRun(label, bold=True)],
            )
        ]
        note_text = str(body or "").strip()
        if note_text:
            paragraphs.append(
                cls(style=_AUDIT_NOTE_STYLE, runs=[OdtTextRun(note_text, bold=False)])
            )
        return paragraphs


@dataclass
class OdtRichContent:
    """Bohatý ODT obsah, který nahradí celý odstavec s placeholdérem."""

    paragraphs: list[OdtParagraph] = field(default_factory=list)

    def plain_text(self) -> str:
        """Textová reprezentace pro testy a ladění (bez ODF markup)."""
        lines: list[str] = []
        for paragraph in self.paragraphs:
            if paragraph.blank:
                lines.append("")
                continue
            if paragraph.image_path is not None:
                lines.append(odt_image_marker(paragraph.image_path))
                continue
            lines.append("".join(run.text for run in paragraph.runs))
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.plain_text()


class OdtExportEngine:
    """
    Univerzální exportní engine pro ODT šablony.

    Šablona používá placeholdery ve tvaru:
        ${nazev_polozky}

    Běžné textové hodnoty jsou escapované pro ODT/XML a nové řádky jsou
    převedené na <text:line-break/>.

    ``OdtRichContent`` nahradí celý odstavec s placeholdérem sadou samostatných
    ``text:p`` (včetně fotografií se stylovaným ``draw:frame``).
    """

    PLACEHOLDER_RE = re.compile(r"\$\{([A-Za-z0-9_]+)\}")
    _MAX_IMAGE_WIDTH_CM = 12.0
    _MAX_IMAGE_HEIGHT_CM = 15.0
    _IMAGE_STYLE_NAME = _EXPORT_IMAGE_STYLE

    def render(
        self, template_path: str | Path, output_path: str | Path, values: Mapping[str, Any]
    ) -> Path:
        template = Path(template_path)
        output = Path(output_path)

        if not template.exists():
            raise FileNotFoundError(f"Šablona nebyla nalezena: {template}")

        if template.suffix.lower() != ".odt":
            raise OdtExportError(f"Šablona musí být ODT soubor: {template}")

        output.parent.mkdir(parents=True, exist_ok=True)

        image_registry: list[tuple[str, Path]] = []
        needs_export_styles = False
        normalized_values: dict[str, Any] = {}

        for key, value in dict(values or {}).items():
            key_text = str(key)
            if isinstance(value, OdtRichContent):
                normalized_values[key_text] = self._render_rich_content(
                    value, image_registry
                )
                needs_export_styles = True
            else:
                escaped = self._escape_odt_text(value, image_registry)
                normalized_values[key_text] = escaped
                if ODT_IMAGE_MARKER_RE.search("" if value is None else str(value)):
                    needs_export_styles = True

        if image_registry:
            needs_export_styles = True

        try:
            with zipfile.ZipFile(template, "r") as zin, zipfile.ZipFile(output, "w") as zout:
                written_names: set[str] = set()
                for item in zin.infolist():
                    data = zin.read(item.filename)

                    if item.filename == "content.xml":
                        xml = data.decode("utf-8")
                        if needs_export_styles or image_registry:
                            xml = self._ensure_drawing_namespaces(xml)
                            xml = self._inject_automatic_styles(xml)
                        xml = self._replace_placeholders(xml, normalized_values)
                        data = xml.encode("utf-8")
                    elif item.filename in {"styles.xml", "meta.xml"}:
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

    def _replace_placeholders(self, xml: str, values: Mapping[str, Any]) -> str:
        rich_keys = {
            key
            for key, value in values.items()
            if isinstance(value, str) and value.startswith(_ODT_FRAGMENT_PREFIX)
        }

        if rich_keys:
            def replace_para(match: re.Match[str]) -> str:
                key = match.group("key")
                if key not in rich_keys:
                    return match.group(0)
                fragment = str(values.get(key, "")).removeprefix(_ODT_FRAGMENT_PREFIX)
                before = (match.group("before") or "").strip()
                after = (match.group("after") or "").strip()
                attrs = match.group("attrs") or ""
                parts: list[str] = []
                if before:
                    parts.append(f"<text:p{attrs}>{before}</text:p>")
                parts.append(fragment)
                if after:
                    parts.append(f"<text:p{attrs}>{after}</text:p>")
                # Fragment je seznam sourozeneckých text:p – nikdy ne vnořovat.
                return "".join(parts)

            xml = _PLACEHOLDER_PARA_RE.sub(replace_para, xml)

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            value = values.get(key, "")
            if isinstance(value, str) and value.startswith(_ODT_FRAGMENT_PREFIX):
                # Odstavec s placeholdérem už byl nahrazen výše; zbylý výskyt
                # (např. mimo text:p) vyprázdni – nikdy nevkládej fragment inline.
                return ""
            return "" if value is None else str(value)

        return self.PLACEHOLDER_RE.sub(repl, xml)

    def _render_rich_content(
        self,
        content: OdtRichContent,
        image_registry: list[tuple[str, Path]],
    ) -> str:
        parts: list[str] = []
        for paragraph in content.paragraphs:
            parts.append(self._render_paragraph(paragraph, image_registry))
        if not parts:
            parts.append('<text:p text:style-name="Standard"/>')
        return _ODT_FRAGMENT_PREFIX + "".join(parts)

    def _render_paragraph(
        self,
        paragraph: OdtParagraph,
        image_registry: list[tuple[str, Path]],
    ) -> str:
        style = xml_escape(paragraph.style or "Standard")
        if paragraph.blank:
            return f'<text:p text:style-name="{style}"/>'

        if paragraph.image_path is not None:
            frame = self._image_frame_xml(str(paragraph.image_path), image_registry)
            if not frame:
                return f'<text:p text:style-name="{style}"/>'
            return f'<text:p text:style-name="{style}">{frame}</text:p>'

        inner_parts: list[str] = []
        for run in paragraph.runs:
            escaped = self._escape_plain_text(run.text)
            if not escaped:
                continue
            if run.bold:
                inner_parts.append(
                    f'<text:span text:style-name="{_AUDIT_BOLD_STYLE}">{escaped}</text:span>'
                )
            else:
                inner_parts.append(escaped)
        inner = "".join(inner_parts)
        if not inner:
            return f'<text:p text:style-name="{style}"/>'
        return f'<text:p text:style-name="{style}">{inner}</text:p>'

    def _escape_odt_text(self, value: Any, image_registry: list[tuple[str, Path]]) -> str:
        text = "" if value is None else str(value)
        parts: list[str] = []
        last = 0
        for match in ODT_IMAGE_MARKER_RE.finditer(text):
            parts.append(self._escape_plain_text(text[last:match.start()]))
            image_xml = self._image_frame_xml(match.group(1).strip(), image_registry)
            if image_xml:
                # Inline fallback (protokol / starší hodnoty): stylovaný frame.
                parts.append(image_xml)
            last = match.end()
        parts.append(self._escape_plain_text(text[last:]))
        return "".join(parts)

    @staticmethod
    def _escape_plain_text(text: str) -> str:
        escaped = html.escape(text, quote=False)
        return escaped.replace("\r\n", "\n").replace("\r", "\n").replace(
            "\n", "<text:line-break/>"
        )

    def _image_frame_xml(
        self, path_text: str, image_registry: list[tuple[str, Path]]
    ) -> str:
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
            f'<draw:frame draw:style-name="{self._IMAGE_STYLE_NAME}" '
            f'draw:name="{name}" text:anchor-type="as-char" '
            f'svg:width="{width_cm:.2f}cm" svg:height="{height_cm:.2f}cm" '
            f'draw:z-index="0">'
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
            return self._MAX_IMAGE_WIDTH_CM, min(
                self._MAX_IMAGE_HEIGHT_CM, self._MAX_IMAGE_WIDTH_CM * 0.75
            )

        # Předpoklad ~96 DPI pro běžné fotografie z mobilu / fotoaparátu.
        width_cm = width_px * 2.54 / 96.0
        height_cm = height_px * 2.54 / 96.0
        scale = min(
            self._MAX_IMAGE_WIDTH_CM / width_cm,
            self._MAX_IMAGE_HEIGHT_CM / height_cm,
            1.0,
        )
        return width_cm * scale, height_cm * scale

    @staticmethod
    def _ensure_drawing_namespaces(xml: str) -> str:
        if "xmlns:draw=" not in xml:
            xml = xml.replace(
                "<office:document-content ",
                '<office:document-content '
                'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" ',
                1,
            )
        if "xmlns:xlink=" not in xml:
            xml = xml.replace(
                "<office:document-content ",
                '<office:document-content '
                'xmlns:xlink="http://www.w3.org/1999/xlink" ',
                1,
            )
        return xml

    def _inject_automatic_styles(self, content_xml: str) -> str:
        styles = self._export_automatic_styles_xml()
        if self._IMAGE_STYLE_NAME in content_xml and _AUDIT_NOTE_STYLE in content_xml:
            return content_xml
        if "</office:automatic-styles>" in content_xml:
            return content_xml.replace(
                "</office:automatic-styles>",
                styles + "</office:automatic-styles>",
                1,
            )
        if "<office:body>" in content_xml:
            return content_xml.replace(
                "<office:body>",
                f"<office:automatic-styles>{styles}</office:automatic-styles><office:body>",
                1,
            )
        return content_xml

    @staticmethod
    def _export_automatic_styles_xml() -> str:
        return (
            # Samostatný grafický styl (ekvivalent běžného Graphics / bez obtékání).
            f'<style:style style:name="{_EXPORT_IMAGE_STYLE}" style:family="graphic">'
            "<style:graphic-properties "
            'text:anchor-type="as-char" '
            'style:wrap="none" '
            'style:vertical-pos="top" '
            'style:vertical-rel="baseline" '
            'style:horizontal-pos="left" '
            'style:horizontal-rel="paragraph" '
            'fo:margin-left="0cm" fo:margin-right="0cm" '
            'fo:margin-top="0.15cm" fo:margin-bottom="0.25cm" '
            'style:flow-with-text="true"/>'
            "</style:style>"
            f'<style:style style:name="{_AUDIT_NOTE_STYLE}" style:family="paragraph">'
            "<style:paragraph-properties "
            'fo:margin-left="0.7cm" fo:margin-right="0cm" '
            'fo:margin-top="0.08cm" fo:margin-bottom="0.08cm"/>'
            '<style:text-properties style:font-name="Liberation Serif" fo:font-size="11pt"/>'
            "</style:style>"
            f'<style:style style:name="{_AUDIT_CRITERION_STYLE}" style:family="paragraph">'
            "<style:paragraph-properties "
            'fo:margin-top="0.25cm" fo:margin-bottom="0.1cm"/>'
            '<style:text-properties style:font-name="Liberation Serif" '
            'fo:font-size="11pt" fo:font-weight="bold"/>'
            "</style:style>"
            f'<style:style style:name="{_AUDIT_BOLD_STYLE}" style:family="text">'
            '<style:text-properties fo:font-weight="bold"/>'
            "</style:style>"
        )

    @staticmethod
    def _inject_manifest_images(
        manifest_xml: str, image_registry: list[tuple[str, Path]]
    ) -> str:
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
            return manifest_xml.replace(
                "</manifest:manifest>", injection + "</manifest:manifest>"
            )
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


def export_odt_template(
    template_path: str | Path, output_path: str | Path, values: Mapping[str, Any]
) -> Path:
    return OdtExportEngine().render(template_path, output_path, values)


def odt_image_marker(path: str | Path) -> str:
    """Vrátí značku pro vložení obrázku do textové hodnoty ODT exportu."""
    return f"[[[ODT_IMAGE|{Path(path)}]]]"


def odt_rich(paragraphs: Sequence[OdtParagraph]) -> OdtRichContent:
    """Pomůcka pro sestavení bohatého ODT obsahu."""
    return OdtRichContent(paragraphs=list(paragraphs))


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
