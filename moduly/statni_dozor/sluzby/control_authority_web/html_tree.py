"""Jednoduchý strom HTML bez regulárních výrazů nad značkami."""

from __future__ import annotations

from html.parser import HTMLParser

_VOID = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
_SKIP_TAGS = frozenset({"script", "style", "noscript"})


class HtmlNode:
    def __init__(self, tag: str, attrs: dict[str, str | None]):
        self.tag = tag
        self.attrs = attrs
        self.children: list[HtmlNode | str] = []
        self.parent: HtmlNode | None = None

    def get(self, name: str) -> str | None:
        return self.attrs.get(name) or self.attrs.get(name.lower())

    def class_names(self) -> set[str]:
        raw = self.get("class") or ""
        return {part for part in raw.split() if part}

    def has_class(self, name: str) -> bool:
        return name in self.class_names()


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HtmlNode("document", {})
        self._current = self.root
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        name = tag.lower()
        if self._skip_depth:
            if name not in _VOID:
                self._skip_depth += 1
            return
        if name in _SKIP_TAGS:
            self._skip_depth = 1
            return
        node = HtmlNode(name, {str(key).lower(): value for key, value in attrs})
        node.parent = self._current
        self._current.children.append(node)
        if name not in _VOID:
            self._current = node

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if self._skip_depth:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if name in _VOID:
            return
        cursor = self._current
        while cursor is not None and cursor.tag != name:
            cursor = cursor.parent
        if cursor is not None and cursor.parent is not None:
            self._current = cursor.parent

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if data:
            self._current.children.append(data)


def parse_html_tree(html: str) -> HtmlNode:
    builder = _TreeBuilder()
    builder.feed(html or "")
    builder.close()
    return builder.root


def iter_nodes(node: HtmlNode) -> list[HtmlNode]:
    found: list[HtmlNode] = []
    stack = [node]
    while stack:
        current = stack.pop()
        found.append(current)
        for child in reversed(current.children):
            if isinstance(child, HtmlNode):
                stack.append(child)
    return found


def node_text(node: HtmlNode) -> str:
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        elif isinstance(child, HtmlNode):
            parts.append(node_text(child))
    return "".join(parts)
