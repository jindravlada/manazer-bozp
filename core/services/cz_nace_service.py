import json
import re

from core.paths import project_root

_DASH_TRANSLATION = str.maketrans({"–": "-", "—": "-", "−": "-"})


def _label_key(text: str) -> str:
    return " ".join(text.translate(_DASH_TRANSLATION).split())


def _digits(code: str) -> str:
    return re.sub(r"[^0-9]", "", str(code))


class CzNaceService:
    def __init__(self):
        self.file_path = project_root() / "zdroje" / "ciselniky" / "cz_nace.json"
        self._items = None
        self._by_kod: dict[str, dict] = {}
        self._by_display: dict[str, dict] = {}
        self._by_label_key: dict[str, dict | None] = {}
        self._by_key: dict[str, list[dict]] = {}

    def _load(self):
        if self._items is not None:
            return

        self._items = []
        self._by_kod = {}
        self._by_display = {}
        self._by_label_key = {}
        self._by_key = {}

        if not self.file_path.exists():
            return

        self._items = json.loads(self.file_path.read_text(encoding="utf-8"))

        for item in self._items:
            code = self._item_code(item)
            if not code:
                continue

            self._by_kod.setdefault(code.casefold(), item)
            display = self._item_display(item)
            self._by_display.setdefault(display, item)
            label_key = _label_key(display)
            if label_key in self._by_label_key:
                self._by_label_key[label_key] = None
            else:
                self._by_label_key[label_key] = item

            for key in self._code_keys(code):
                bucket = self._by_key.setdefault(key, [])
                if item not in bucket:
                    bucket.append(item)

    def _item_code(self, item: dict) -> str:
        return str(item.get("kod", "")).strip()

    def _item_display(self, item: dict) -> str:
        code = self._item_code(item)
        return item.get("display") or f"{code} – {item.get('nazev', '')}"

    def _code_keys(self, code: str) -> list[str]:
        code = str(code).strip()
        compact = re.sub(r"[^0-9A-Za-z]", "", code).upper()
        keys: list[str] = []

        def add(value: str) -> None:
            text = str(value).strip().upper()
            if text and text not in keys:
                keys.append(text)
            folded = re.sub(r"[^0-9A-Za-z]", "", text).upper()
            if folded and folded not in keys:
                keys.append(folded)

        add(code)
        add(compact)
        if compact.isdigit():
            if len(compact) == 5 and compact.endswith("0"):
                add(compact[:4])
            if len(compact) == 4:
                add(f"{compact[:2]}.{compact[2:]}")
                add(f"{compact[:2]}.{compact[2:]}.0")
            if len(compact) == 5:
                add(f"{compact[:2]}.{compact[2:4]}.{compact[4]}")
            if len(compact) == 3:
                add(f"{compact[:2]}.{compact[2]}")
            if len(compact) == 2:
                add(compact)

        return keys

    def lookup(self, value: str) -> tuple[str, str] | None:
        """Vrátí (kód, zobrazení) položky číselníku, nebo None když ji nelze určit."""
        self._load()
        raw = str(value or "").strip()
        if not raw:
            return None

        item = self._by_display.get(raw)
        if item is None:
            item = self._by_label_key.get(_label_key(raw))
        if item is not None:
            return self._item_code(item), self._item_display(item)

        item = self._by_kod.get(raw.casefold())
        if item is not None:
            return self._item_code(item), self._item_display(item)

        matches: list[dict] = []
        seen: set[int] = set()
        for key in self._code_keys(raw):
            for candidate in self._by_key.get(key, ()):
                marker = id(candidate)
                if marker in seen:
                    continue
                seen.add(marker)
                matches.append(candidate)

        if not matches:
            return None
        if len(matches) == 1:
            chosen = matches[0]
        else:
            chosen = self._prefer_match(raw, matches)
            if chosen is None:
                return None

        return self._item_code(chosen), self._item_display(chosen)

    def _prefer_match(self, raw: str, matches: list[dict]) -> dict | None:
        digits = _digits(raw)
        if len(digits) == 5 and digits.endswith("0"):
            class_digits = digits[:4]
            class_matches = [
                item for item in matches if _digits(self._item_code(item)) == class_digits
            ]
            if len(class_matches) == 1:
                return class_matches[0]
        return None

    def resolve(self, value: str) -> tuple[str, str]:
        """Vrátí (kód, zobrazení). Neznámá hodnota zůstane v obou složkách beze změny."""
        raw = str(value or "").strip()
        found = self.lookup(raw)
        if found is None:
            return raw, raw
        return found

    def entries(self) -> list[tuple[str, str]]:
        """Položky číselníku jako (kód, zobrazení)."""
        self._load()
        result: list[tuple[str, str]] = []
        for item in self._items:
            code = self._item_code(item)
            if not code:
                continue
            result.append((code, self._item_display(item)))
        return result

    def get_display(self, code: str) -> str:
        _stored, display = self.resolve(code)
        return display

    def get_displays(self, codes: list[str]) -> list[str]:
        result = []
        seen = set()

        for code in codes:
            display = self.get_display(code)
            if display and display not in seen:
                result.append(display)
                seen.add(display)

        return result

    def get_all_displays(self) -> list[str]:
        return [display for _code, display in self.entries()]


cz_nace_service = CzNaceService()
