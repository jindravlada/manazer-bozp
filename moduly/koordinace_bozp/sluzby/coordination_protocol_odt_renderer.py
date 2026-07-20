"""Vykreslení koordinačního protokolu do ODT (BUILDER-COORD-1 / 1a).

Renderer nepřistupuje k databázi ani neskládá osnovu dokumentu.
Vykresluje výhradně ``protocol_data["document"]["blocks"]``.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, Mapping

from core.export.odt_engine import _sync_written_file
from moduly.koordinace_bozp.constants import (
    PROTOCOL_APPENDIX_A,
    PROTOCOL_APPENDIX_B,
    PROTOCOL_APPENDIX_C,
    PROTOCOL_APPENDIX_OVERVIEW,
    PROTOCOL_PAGE_FOOTER,
    PROTOCOL_SECTION_ACTIVITIES,
    PROTOCOL_SECTION_BASICS,
    PROTOCOL_SECTION_CONCLUSIONS,
    PROTOCOL_SECTION_PARTICIPANTS,
    PROTOCOL_SECTION_WORKPLACES,
    PROTOCOL_TITLE,
)
from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
    ProtocolBuildResult,
)
from moduly.koordinace_bozp.sluzby.coordination_protocol_document import (
    BLOCK_KIND_BLANK,
    BLOCK_KIND_BULLET,
    BLOCK_KIND_HEADING,
    BLOCK_KIND_INDENTED,
    BLOCK_KIND_NUMBERED_HEADING,
    BLOCK_KIND_PARAGRAPH,
    BLOCK_KIND_PBP_RULE,
    BLOCK_KIND_SIGNATURE_LINE,
    BLOCK_KIND_SUBTITLE,
    BLOCK_KIND_TITLE,
    BLOCK_STYLE_BULLET,
    BLOCK_STYLE_EMPLOYER_ABBR,
    BLOCK_STYLE_HEADING,
    BLOCK_STYLE_INDENTED,
    BLOCK_STYLE_LABEL,
    BLOCK_STYLE_PBP_RULE,
    BLOCK_STYLE_TITLE,
    document_blocks_from_dict,
    render_blocks_to_plain_lines,
)


class CoordinationProtocolOdtRendererError(ValueError):
    pass


# Hlavní nadpisy dokumentu – pro testy pořadí sekcí.
PROTOCOL_ODT_CHAPTER_TITLES = (
    PROTOCOL_TITLE,
    PROTOCOL_SECTION_BASICS,
    PROTOCOL_SECTION_PARTICIPANTS,
    PROTOCOL_SECTION_WORKPLACES,
    PROTOCOL_SECTION_ACTIVITIES,
    PROTOCOL_SECTION_CONCLUSIONS,
    PROTOCOL_APPENDIX_OVERVIEW,
    PROTOCOL_APPENDIX_A,
    PROTOCOL_APPENDIX_B,
    PROTOCOL_APPENDIX_C,
)


class CoordinationProtocolOdtRenderer:
    """Vykreslí ODT z připravených bloků protokolu."""

    def render(
        self,
        output_path: str | Path,
        *,
        protocol_data: Mapping[str, Any],
        warnings: Any = None,
        summary: Any = None,
    ) -> Path:
        del warnings, summary
        if protocol_data is None:
            raise CoordinationProtocolOdtRendererError("protocol_data je povinné.")
        blocks = document_blocks_from_dict(protocol_data.get("document"))
        if not blocks:
            raise CoordinationProtocolOdtRendererError(
                "protocol_data neobsahuje dokument protokolu."
            )
        return self._write_odt(Path(output_path), blocks=blocks)

    def render_from_result(
        self,
        output_path: str | Path,
        result: ProtocolBuildResult | Mapping[str, Any],
    ) -> Path:
        if isinstance(result, ProtocolBuildResult):
            return self.render(output_path, protocol_data=result.protocol_data)
        if not isinstance(result, Mapping):
            raise CoordinationProtocolOdtRendererError(
                "Výsledek sestavení protokolu má neplatný tvar."
            )
        return self.render(
            output_path,
            protocol_data=result.get("protocol_data") or {},
        )

    def render_blocks(
        self,
        output_path: str | Path,
        blocks: list,
    ) -> Path:
        return self._write_odt(
            Path(output_path),
            blocks=document_blocks_from_dict({"blocks": blocks}),
        )

    def _style_for_block(self, block) -> str:
        if block.kind == BLOCK_KIND_TITLE:
            return "ProtocolTitle"
        if block.kind in (BLOCK_KIND_HEADING, BLOCK_KIND_NUMBERED_HEADING):
            return "ProtocolHeading"
        if block.kind == BLOCK_KIND_SUBTITLE:
            return "ProtocolSubtitle"
        if block.kind == BLOCK_KIND_BULLET:
            return "ProtocolBullet"
        if block.kind == BLOCK_KIND_INDENTED:
            return "ProtocolIndented"
        if block.kind == BLOCK_KIND_PBP_RULE or block.style == BLOCK_STYLE_PBP_RULE:
            return "ProtocolPbpRule"
        if block.style == BLOCK_STYLE_TITLE:
            return "ProtocolTitle"
        if block.style == BLOCK_STYLE_HEADING:
            return "ProtocolHeading"
        if block.style == BLOCK_STYLE_BULLET:
            return "ProtocolBullet"
        if block.style == BLOCK_STYLE_EMPLOYER_ABBR:
            return "ProtocolEmployerAbbr"
        if block.style == BLOCK_STYLE_LABEL:
            return "ProtocolLabel"
        if block.style == BLOCK_STYLE_INDENTED:
            return "ProtocolIndented"
        if block.bold:
            return "ProtocolBoldPara"
        return "ProtocolBody"

    def _text_for_block(self, block) -> str:
        text = (block.text or "").strip()
        if block.kind == BLOCK_KIND_NUMBERED_HEADING:
            return f"{block.level}. {text}" if text else f"{block.level}."
        if block.kind == BLOCK_KIND_BULLET:
            return f"• {text}" if text else "•"
        return text

    def _inner_xml_for_block(self, block) -> str:
        if block.runs:
            parts: list[str] = []
            for text, is_bold in block.runs:
                escaped = self._escape_xml(str(text))
                if is_bold:
                    parts.append(
                        f'<text:span text:style-name="ProtocolBold">{escaped}</text:span>'
                    )
                else:
                    parts.append(escaped)
            return "".join(parts)
        text = self._text_for_block(block)
        escaped = self._escape_xml(text)
        if block.bold and text:
            return f'<text:span text:style-name="ProtocolBold">{escaped}</text:span>'
        return escaped

    def _blocks_to_paragraphs_xml(self, blocks) -> str:
        parts: list[str] = []
        for block in blocks:
            style = self._style_for_block(block)
            if block.kind == BLOCK_KIND_BLANK:
                parts.append(f'<text:p text:style-name="{style}"/>')
                continue
            inner = self._inner_xml_for_block(block)
            if inner:
                parts.append(f'<text:p text:style-name="{style}">{inner}</text:p>')
            else:
                parts.append(f'<text:p text:style-name="{style}"/>')
        return "".join(parts)

    def _styles_xml(self) -> str:
        footer_label = self._escape_xml(PROTOCOL_PAGE_FOOTER)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<office:document-styles '
            'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
            'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
            'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
            'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
            'office:version="1.2">'
            "<office:styles>"
            '<style:style style:name="ProtocolTitle" style:family="paragraph">'
            '<style:text-properties fo:font-size="16pt" fo:font-weight="bold" '
            'style:font-name="Liberation Serif"/>'
            '<style:paragraph-properties fo:text-align="center" fo:margin-bottom="0.35cm"/>'
            "</style:style>"
            '<style:style style:name="ProtocolSubtitle" style:family="paragraph">'
            '<style:text-properties fo:font-size="12pt" fo:font-weight="bold" '
            'style:font-name="Liberation Serif"/>'
            '<style:paragraph-properties fo:text-align="center" fo:margin-bottom="0.35cm"/>'
            "</style:style>"
            '<style:style style:name="ProtocolHeading" style:family="paragraph">'
            '<style:text-properties fo:font-size="12pt" fo:font-weight="bold" '
            'style:font-name="Liberation Serif"/>'
            '<style:paragraph-properties fo:margin-top="0.35cm" fo:margin-bottom="0.15cm"/>'
            "</style:style>"
            '<style:style style:name="ProtocolBody" style:family="paragraph">'
            '<style:text-properties fo:font-size="11pt" style:font-name="Liberation Serif"/>'
            '<style:paragraph-properties fo:margin-bottom="0.12cm"/>'
            "</style:style>"
            '<style:style style:name="ProtocolBoldPara" style:family="paragraph">'
            '<style:text-properties fo:font-size="11pt" fo:font-weight="bold" '
            'style:font-name="Liberation Serif"/>'
            '<style:paragraph-properties fo:margin-bottom="0.08cm"/>'
            "</style:style>"
            '<style:style style:name="ProtocolEmployerAbbr" style:family="paragraph">'
            '<style:text-properties fo:font-size="11pt" fo:font-weight="bold" '
            'style:font-name="Liberation Serif"/>'
            '<style:paragraph-properties fo:margin-top="0.15cm" fo:margin-bottom="0.02cm"/>'
            "</style:style>"
            '<style:style style:name="ProtocolLabel" style:family="paragraph">'
            '<style:text-properties fo:font-size="11pt" fo:font-weight="bold" '
            'style:font-name="Liberation Serif"/>'
            '<style:paragraph-properties fo:margin-top="0.2cm" fo:margin-bottom="0.1cm"/>'
            "</style:style>"
            '<style:style style:name="ProtocolBullet" style:family="paragraph">'
            '<style:text-properties fo:font-size="11pt" style:font-name="Liberation Serif"/>'
            '<style:paragraph-properties fo:margin-left="0.75cm" fo:margin-bottom="0.08cm"/>'
            "</style:style>"
            '<style:style style:name="ProtocolIndented" style:family="paragraph">'
            '<style:text-properties fo:font-size="11pt" style:font-name="Liberation Serif"/>'
            '<style:paragraph-properties fo:margin-left="1.35cm" fo:margin-bottom="0.04cm"/>'
            "</style:style>"
            '<style:style style:name="ProtocolPbpRule" style:family="paragraph">'
            '<style:text-properties fo:font-size="11pt" style:font-name="Liberation Serif"/>'
            '<style:paragraph-properties fo:margin-top="0.2cm" fo:margin-bottom="0.15cm"/>'
            "</style:style>"
            '<style:style style:name="ProtocolBold" style:family="text">'
            '<style:text-properties fo:font-weight="bold"/>'
            "</style:style>"
            '<style:style style:name="ProtocolFooter" style:family="paragraph">'
            '<style:text-properties fo:font-size="9pt" style:font-name="Liberation Serif"/>'
            '<style:paragraph-properties fo:text-align="end"/>'
            "</style:style>"
            "</office:styles>"
            "<office:automatic-styles>"
            '<style:page-layout style:name="pm1">'
            '<style:page-layout-properties fo:page-width="21.001cm" '
            'fo:page-height="29.7cm" style:num-format="1" '
            'style:print-orientation="portrait" fo:margin-top="2cm" '
            'fo:margin-bottom="2cm" fo:margin-left="2cm" fo:margin-right="2cm"/>'
            "<style:header-style/>"
            "<style:footer-style>"
            '<style:header-footer-properties fo:min-height="0.6cm" '
            'fo:margin-left="0cm" fo:margin-right="0cm" fo:margin-top="0.35cm"/>'
            "</style:footer-style>"
            "</style:page-layout>"
            "</office:automatic-styles>"
            "<office:master-styles>"
            '<style:master-page style:name="Standard" style:page-layout-name="pm1">'
            "<style:footer>"
            '<text:p text:style-name="ProtocolFooter">'
            f"{footer_label} "
            '<text:page-number text:select-page="current"/>'
            " z "
            "<text:page-count/>"
            "</text:p>"
            "</style:footer>"
            "</style:master-page>"
            "</office:master-styles>"
            "</office:document-styles>"
        )

    def _write_odt(self, output_path: Path, *, blocks) -> Path:
        paragraphs_xml = self._blocks_to_paragraphs_xml(blocks)
        content_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<office:document-content '
            'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
            'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
            'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
            'office:version="1.2">'
            "<office:body><office:text>"
            f"{paragraphs_xml}"
            "</office:text></office:body></office:document-content>"
        )
        styles_xml = self._styles_xml()
        meta_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<office:document-meta '
            'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'office:version="1.2">'
            "<office:meta/>"
            "</office:document-meta>"
        )
        manifest_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<manifest:manifest '
            'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
            'manifest:version="1.2">'
            '<manifest:file-entry manifest:full-path="/" '
            'manifest:version="1.2" '
            'manifest:media-type="application/vnd.oasis.opendocument.text"/>'
            '<manifest:file-entry manifest:full-path="content.xml" '
            'manifest:media-type="text/xml"/>'
            '<manifest:file-entry manifest:full-path="styles.xml" '
            'manifest:media-type="text/xml"/>'
            '<manifest:file-entry manifest:full-path="meta.xml" '
            'manifest:media-type="text/xml"/>'
            "</manifest:manifest>"
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w") as zout:
            info = zipfile.ZipInfo("mimetype")
            info.compress_type = zipfile.ZIP_STORED
            zout.writestr(info, "application/vnd.oasis.opendocument.text")
            zout.writestr("content.xml", content_xml.encode("utf-8"))
            zout.writestr("styles.xml", styles_xml.encode("utf-8"))
            zout.writestr("meta.xml", meta_xml.encode("utf-8"))
            zout.writestr("META-INF/manifest.xml", manifest_xml.encode("utf-8"))
        _sync_written_file(output_path)
        return output_path

    @staticmethod
    def _escape_xml(value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def plain_lines_from_protocol_data(
        self,
        protocol_data: Mapping[str, Any],
    ) -> list[str]:
        blocks = document_blocks_from_dict(protocol_data.get("document"))
        return render_blocks_to_plain_lines(blocks)


coordination_protocol_odt_renderer = CoordinationProtocolOdtRenderer()
