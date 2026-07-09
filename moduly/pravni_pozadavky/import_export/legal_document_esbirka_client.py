import hashlib
import os
import re
from dataclasses import dataclass
from datetime import date
from html import unescape
from pathlib import Path

import requests

ESBIRKA_BASE_URL = "https://www.esbirka.cz/cs"
ESBIRKA_VERSION_CHECKSUM_PREFIX = "esbirka:"
_REQUEST_TIMEOUT = 60
_FRAGS_START = '<div class="Frags">'
_FRAGS_ARTICLE_END = "</article>"
_NOT_FOUND_MARKER = "Stránka nenalezena"
_ELEMENT_RE = re.compile(
    r"<(p|h3)\s+class=\"([^\"]*)\"[^>]*>(.*?)</\1>",
    re.DOTALL | re.IGNORECASE,
)
_OG_TITLE_RE = re.compile(r'property="og:title"\s+content="([^"]*)"', re.IGNORECASE)
_H1_TITLE_RE = re.compile(
    r"<h1[^>]*>.*?<span class=\"h1a\">(.*?)</span>",
    re.DOTALL | re.IGNORECASE,
)
_TITLE_PREFIX_RE = re.compile(r"^\d+/\d+\s+Sb\.\s*", re.IGNORECASE)
_CONTENT_LEVEL_RE = re.compile(r"^L(\d+)$", re.IGNORECASE)
_LETTER_MARKER_RE = re.compile(
    r"<var>[a-záčďéěíňóřšťúůýž]\)</var>",
    re.IGNORECASE,
)
_SUBSECTION_MARKER_RE = re.compile(r"<var>\(\d+\)</var>")
_DEBUG_TXT_ENV = "LEGAL_DOCUMENT_ESBIRKA_DEBUG_TXT"
_H1_META_RE = re.compile(
    r'<h1[^>]*data-docid="([^"]*)"[^>]*data-sliceid="([^"]*)"',
    re.IGNORECASE,
)
_PUBLICATION_DATE_RE = re.compile(
    r"ze dne (\d{1,2})\.\s*([a-záčďéěíňóřšťúůýž]+)\s+(\d{4})",
    re.IGNORECASE,
)
_CZECH_MONTHS = {
    "ledna": 1,
    "února": 2,
    "unora": 2,
    "března": 3,
    "brezna": 3,
    "dubna": 4,
    "května": 5,
    "kvetna": 5,
    "června": 6,
    "cervna": 6,
    "července": 7,
    "cervence": 7,
    "srpna": 8,
    "září": 9,
    "zari": 9,
    "října": 10,
    "rijna": 10,
    "listopadu": 11,
    "prosince": 12,
}


@dataclass(frozen=True)
class ESbirkaVersionInfo:
    doc_id: str
    slice_id: str
    source_url: str
    publication_date: date | None
    text_checksum: str
    version_label: str


class LegalDocumentESbirkaClient:
    def fetch_version_info(self, *, year: int, number: str) -> ESbirkaVersionInfo:
        html = self.fetch_full_text_html(year=year, number=number)
        return self.extract_version_info(
            html,
            year=year,
            number=number,
        )

    def extract_version_info(
        self,
        html: str,
        *,
        year: int,
        number: str,
    ) -> ESbirkaVersionInfo:
        doc_id, slice_id = self._extract_version_ids(html)
        source_url = self.build_url(year=year, number=number)
        raw_text = self.html_to_text(html)
        return ESbirkaVersionInfo(
            doc_id=doc_id,
            slice_id=slice_id,
            source_url=source_url,
            publication_date=self._extract_publication_date(html),
            text_checksum=self.compute_text_checksum(raw_text),
            version_label=f"e-Sbírka {slice_id}",
        )

    def compute_text_checksum(self, text: str) -> str:
        normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def build_version_checksum(self, *, slice_id: str, text_checksum: str) -> str:
        return f"{ESBIRKA_VERSION_CHECKSUM_PREFIX}{slice_id}:{text_checksum}"

    def parse_version_checksum(self, checksum: str) -> tuple[str | None, str | None]:
        normalized = (checksum or "").strip()
        if not normalized.startswith(ESBIRKA_VERSION_CHECKSUM_PREFIX):
            return None, None
        payload = normalized[len(ESBIRKA_VERSION_CHECKSUM_PREFIX):]
        slice_id, separator, text_checksum = payload.partition(":")
        if not separator:
            return None, None
        return slice_id or None, text_checksum or None

    def _extract_version_ids(self, html: str) -> tuple[str, str]:
        match = _H1_META_RE.search(html)
        if match is None:
            raise ValueError("Neočekávaný formát stránky.")
        doc_id = match.group(1).strip()
        slice_id = match.group(2).strip()
        if not doc_id or not slice_id:
            raise ValueError("Neočekávaný formát stránky.")
        return doc_id, slice_id

    def _extract_publication_date(self, html: str) -> date | None:
        frags_html = self._extract_frags_html(html)
        match = _PUBLICATION_DATE_RE.search(frags_html)
        if match is None:
            return None
        day = int(match.group(1))
        month_name = match.group(2).casefold().replace("ů", "u")
        month = _CZECH_MONTHS.get(month_name)
        if month is None:
            return None
        year = int(match.group(3))
        return date(year, month, day)

    def build_url(self, *, year: int, number: str) -> str:
        normalized_number = (number or "").strip()
        if not normalized_number:
            raise ValueError("Číslo předpisu je povinné.")
        return f"{ESBIRKA_BASE_URL}/{year}-{normalized_number}"

    def fetch_full_text_html(self, *, year: int, number: str) -> str:
        url = self.build_url(year=year, number=number)
        try:
            response = requests.get(url, timeout=_REQUEST_TIMEOUT, allow_redirects=True)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ValueError("Internet není dostupný.") from exc

        html = response.text
        if _NOT_FOUND_MARKER in html:
            raise ValueError("Předpis nenalezen.")
        if _FRAGS_START not in html:
            raise ValueError("Neočekávaný formát stránky.")
        return html

    def extract_title(self, html: str) -> str:
        h1_match = _H1_TITLE_RE.search(html)
        if h1_match:
            title = self._strip_tags(h1_match.group(1))
            if title:
                return title

        og_match = _OG_TITLE_RE.search(html)
        if og_match:
            title = unescape(og_match.group(1)).strip()
            title = _TITLE_PREFIX_RE.sub("", title)
            title = re.sub(r"\s*\.\.\.\s*$", "", title).strip()
            if title:
                return title

        raise ValueError("Neočekávaný formát stránky.")

    def html_to_text(self, html: str, *, debug_txt_path: str | Path | None = None) -> str:
        frags_html = self._extract_frags_html(html)
        lines: list[str] = []

        for _tag, class_attr, inner_html in _ELEMENT_RE.findall(frags_html):
            classes = {value.upper() for value in class_attr.split()}
            if "CAST" in classes:
                lines.append(self._element_to_line(inner_html))
                continue
            if "HLAVA" in classes and "SIL" not in classes:
                lines.append(self._element_to_line(inner_html))
                continue
            if "DIL" in classes:
                lines.append(self._element_to_line(inner_html))
                continue
            if "PARA" in classes:
                lines.append(self._element_to_line(inner_html))
                continue
            if "NADPIS" in classes:
                lines.append(self._element_to_line(inner_html))
                continue
            if self._should_extract_content_line(classes, inner_html):
                line = self._element_to_line(inner_html)
                if line:
                    lines.append(line)

        text = "\n".join(line for line in lines if line)
        if not text.strip():
            raise ValueError("Neočekávaný formát stránky.")

        resolved_debug_path = debug_txt_path or os.environ.get(_DEBUG_TXT_ENV)
        if resolved_debug_path:
            Path(resolved_debug_path).write_text(text + "\n", encoding="utf-8")

        return text + "\n"

    def _should_extract_content_line(self, classes: set[str], inner_html: str) -> bool:
        # Zákoník práce používá L4/L5, nařízení vlády často L2/L3 pro odstavce a písmena.
        if self._is_content_level(classes):
            return True
        if _LETTER_MARKER_RE.search(inner_html):
            return True
        if _SUBSECTION_MARKER_RE.search(inner_html):
            return True
        return False

    def _is_content_level(self, classes: set[str]) -> bool:
        for class_name in classes:
            match = _CONTENT_LEVEL_RE.match(class_name)
            if match is not None and int(match.group(1)) >= 2:
                return True
        return False

    def _extract_frags_html(self, html: str) -> str:
        start = html.find(_FRAGS_START)
        if start < 0:
            raise ValueError("Neočekávaný formát stránky.")

        content_start = start + len(_FRAGS_START)
        end = html.find(_FRAGS_ARTICLE_END, content_start)
        if end < 0:
            end = len(html)
        return html[content_start:end]

    def _element_to_line(self, inner_html: str) -> str:
        content = inner_html
        content = re.sub(r"<br\s*/?>", " ", content, flags=re.IGNORECASE)
        content = re.sub(
            r"<a[^>]*class=\"linknote\"[^>]*>.*?</a>",
            "",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        image_description = self._image_description(content)
        content = re.sub(r"<a[^>]*>", "", content, flags=re.IGNORECASE)
        content = re.sub(r"</a>", "", content, flags=re.IGNORECASE)
        content = re.sub(r"<i[^>]*>.*?</i>", "", content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(
            r"<var>(.*?)</var>",
            r"\1",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        line = self._strip_tags(content)
        if not line and image_description:
            return image_description
        return line

    def _image_description(self, content: str) -> str:
        for pattern in (
            r"<img[^>]*alt=\"([^\"]*)\"",
            r"<a[^>]*title=\"([^\"]*)\"",
        ):
            match = re.search(pattern, content, flags=re.IGNORECASE)
            if match is not None:
                description = unescape(match.group(1)).strip()
                if description:
                    return description
        return ""

    def _strip_tags(self, value: str) -> str:
        text = re.sub(r"<[^>]+>", "", value)
        text = unescape(text)
        return re.sub(r"\s+", " ", text).strip()


legal_document_esbirka_client = LegalDocumentESbirkaClient()
