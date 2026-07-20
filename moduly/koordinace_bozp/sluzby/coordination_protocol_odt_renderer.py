"""Vykreslení koordinačního protokolu do ODT (BUILDER-COORD-1).

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
    BLOCK_KIND_NUMBERED_HEADING,
    BLOCK_KIND_PARAGRAPH,
    BLOCK_KIND_SIGNATURE_LINE,
    BLOCK_KIND_SUBTITLE,
    BLOCK_KIND_TITLE,
    BLOCK_STYLE_BULLET,
    BLOCK_STYLE_HEADING,
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
        return self._write_odt(Path(output_path), blocks=document_blocks_from_dict({"blocks": blocks}))

    def _style_for_block(self, block) -> str:
        if block.kind == BLOCK_KIND_TITLE:
            return "ProtocolTitle"
        if block.kind in (BLOCK_KIND_HEADING, BLOCK_KIND_NUMBERED_HEADING):
            return "ProtocolHeading"
        if block.kind == BLOCK_KIND_SUBTITLE:
            return "ProtocolSubtitle"
        if block.kind == BLOCK_KIND_BULLET:
            return "ProtocolBullet"
        if block.style == BLOCK_STYLE_TITLE:
            return "ProtocolTitle"
        if block.style == BLOCK_STYLE_HEADING:
            return "ProtocolHeading"
        if block.style == BLOCK_STYLE_BULLET:
            return "ProtocolBullet"
        return "ProtocolBody"

    def _text_for_block(self, block) -> str:
        text = (block.text or "").strip()
        if block.kind == BLOCK_KIND_NUMBERED_HEADING:
            return f"{block.level}. {text}" if text else f"{block.level}."
        if block.kind == BLOCK_KIND_BULLET:
            return f"• {text}" if text else "•"
        return text

    def _blocks_to_paragraphs(self, blocks) -> list[tuple[str, str]]:
        paragraphs: list[tuple[str, str]] = []
        for block in blocks:
            if block.kind == BLOCK_KIND_BLANK:
                paragraphs.append(("ProtocolBody", ""))
                continue
            paragraphs.append(
                (self._style_for_block(block), self._text_for_block(block))
            )
        return paragraphs

    def _write_odt(self, output_path: Path, *, blocks) -> Path:
        paragraphs = self._blocks_to_paragraphs(blocks)
        paragraphs_xml = "".join(
            (
                f'<text:p text:style-name="{style}">{self._escape_xml(text)}</text:p>'
                if text
                else f'<text:p text:style-name="{style}"/>'
            )
            for style, text in paragraphs
        )
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
        styles_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<office:document-styles '
            'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
            'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
            'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
            'office:version="1.2">'
            "<office:styles>"
            '<style:style style:name="ProtocolTitle" style:family="paragraph">'
            '<style:text-properties fo:font-size="16pt" fo:font-weight="bold"/>'
            '<style:paragraph-properties fo:text-align="center" fo:margin-bottom="0.35cm"/>'
            "</style:style>"
            '<style:style style:name="ProtocolSubtitle" style:family="paragraph">'
            '<style:text-properties fo:font-size="12pt" fo:font-weight="bold"/>'
            '<style:paragraph-properties fo:text-align="center" fo:margin-bottom="0.35cm"/>'
            "</style:style>"
            '<style:style style:name="ProtocolHeading" style:family="paragraph">'
            '<style:text-properties fo:font-size="12pt" fo:font-weight="bold"/>'
            '<style:paragraph-properties fo:margin-top="0.35cm" fo:margin-bottom="0.15cm"/>'
            "</style:style>"
            '<style:style style:name="ProtocolBody" style:family="paragraph">'
            '<style:text-properties fo:font-size="11pt"/>'
            '<style:paragraph-properties fo:margin-bottom="0.12cm"/>'
            "</style:style>"
            '<style:style style:name="ProtocolBullet" style:family="paragraph">'
            '<style:text-properties fo:font-size="11pt"/>'
            '<style:paragraph-properties fo:margin-left="0.75cm" fo:margin-bottom="0.08cm"/>'
            "</style:style>"
            "</office:styles>"
            "</office:document-styles>"
        )
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
