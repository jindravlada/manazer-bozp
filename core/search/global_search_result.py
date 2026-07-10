"""Společný datový model výsledku globálního vyhledávání."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GlobalSearchResult:
    entity_type: str
    entity_id: int
    title: str
    subtitle: str = ""
    search_text: str = ""
    sort_key: tuple = field(default_factory=tuple)
    group_label: str = ""
    module_key: str = ""
    priority: int = 0
    description: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def source_type(self) -> str:
        return self.entity_type

    @property
    def source_id(self) -> int:
        return self.entity_id

    @property
    def module_label(self) -> str:
        return self.group_label

    @property
    def display(self) -> str:
        if self.subtitle:
            return f"{self.group_label}: {self.title} — {self.subtitle}"
        return f"{self.group_label}: {self.title}"

    @property
    def category(self) -> str:
        return self.group_label

    @property
    def record_id(self) -> int | None:
        if self.entity_type == "action":
            return None
        return self.entity_id

    @property
    def record_type(self) -> str:
        return self.entity_type
