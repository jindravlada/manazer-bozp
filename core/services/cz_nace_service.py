import json
import re
from pathlib import Path


class CzNaceService:
    def __init__(self):
        self.file_path = Path("zdroje/ciselniky/cz_nace.json")
        self._items = None
        self._by_normalized = {}

    def _load(self):
        if self._items is not None:
            return

        if not self.file_path.exists():
            self._items = []
            self._by_normalized = {}
            return

        self._items = json.loads(self.file_path.read_text(encoding="utf-8"))
        self._by_normalized = {}

        for item in self._items:
            code = str(item.get("kod", "")).strip()
            if not code:
                continue

            for key in self._code_keys(code):
                if key not in self._by_normalized:
                    self._by_normalized[key] = item

    def _code_keys(self, code: str) -> set[str]:
        code = str(code).strip()
        digits = re.sub(r"[^0-9A-Za-z]", "", code).upper()

        keys = {code.upper(), digits}

        if digits.isdigit():
            if len(digits) == 5 and digits.endswith("0"):
                keys.add(digits[:4])
            if len(digits) == 4:
                keys.add(f"{digits[:2]}.{digits[2:]}")
                keys.add(f"{digits[:2]}.{digits[2:]}.0")
            if len(digits) == 5:
                keys.add(f"{digits[:2]}.{digits[2:4]}.{digits[4]}")
            if len(digits) == 3:
                keys.add(f"{digits[:2]}.{digits[2]}")
            if len(digits) == 2:
                keys.add(digits)

        normalized = set()
        for key in keys:
            normalized.add(str(key).strip().upper())
            normalized.add(re.sub(r"[^0-9A-Za-z]", "", str(key)).upper())

        return normalized

    def get_display(self, code: str) -> str:
        self._load()

        code = str(code).strip()
        if not code:
            return ""

        for key in self._code_keys(code):
            item = self._by_normalized.get(key)
            if item:
                return item.get("display") or f"{item.get('kod')} – {item.get('nazev')}"

        return code

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
        self._load()
        return [
            item.get("display") or f"{item.get('kod')} – {item.get('nazev')}"
            for item in self._items
            if item.get("kod")
        ]


cz_nace_service = CzNaceService()
