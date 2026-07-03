"""Datový model výsledku globálního vyhledávání."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SearchResult:
    source_type: str
    source_id: int
    title: str
    subtitle: str = ""
    description: str = ""
    module_key: str = ""
    module_label: str = ""
    priority: int = 0
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def display(self) -> str:
        """Zpětná kompatibilita s toolbar completerem (Commit 6 přepíše UI)."""
        if self.subtitle:
            return f"{self.module_label}: {self.title} — {self.subtitle}"
        return f"{self.module_label}: {self.title}"

    @property
    def category(self) -> str:
        return self.module_label

    @property
    def record_id(self) -> int | None:
        if self.source_type == "action":
            return None
        return self.source_id

    @property
    def record_type(self) -> str:
        return self.source_type
