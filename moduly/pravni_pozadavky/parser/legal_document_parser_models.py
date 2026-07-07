from dataclasses import dataclass, field

SECTION_PART = "cast"
SECTION_HEAD = "hlava"
SECTION_DIVISION = "dil"
SECTION_PARAGRAPH = "paragraf"
SECTION_SUBSECTION = "odstavec"
SECTION_LETTER = "pismeno"
SECTION_ATTACHMENT = "priloha"


@dataclass
class ParsedLegalSection:
    section_type: str
    section_number: str = ""
    paragraph: str = ""
    item_letter: str = ""
    title: str = ""
    text: str = ""
    sort_order: int = 0
    parent_sort_order: int | None = None
    note: str = ""

    def to_dict(self) -> dict:
        data = {
            "section_type": self.section_type,
            "section_number": self.section_number,
            "paragraph": self.paragraph,
            "item_letter": self.item_letter,
            "title": self.title,
            "text": self.text,
            "sort_order": self.sort_order,
            "note": self.note,
        }
        if self.parent_sort_order is not None:
            data["parent_sort_order"] = self.parent_sort_order
        return data


@dataclass
class LegalDocumentParseResult:
    document: dict = field(default_factory=dict)
    version: dict = field(default_factory=dict)
    sections: list[ParsedLegalSection] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "document": self.document,
            "version": self.version,
            "sections": [section.to_dict() for section in self.sections],
        }
