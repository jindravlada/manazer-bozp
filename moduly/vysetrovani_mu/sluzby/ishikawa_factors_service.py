import json
from copy import deepcopy
from pathlib import Path

from moduly.vysetrovani_mu.constants import (
    ISHIKAWA_CATEGORIES,
    ISHIKAWA_FALLBACK_CATALOG,
    ISHIKAWA_OTHER_FACTOR,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CATALOG_PATH = _PROJECT_ROOT / "ciselniky/modulove/vysetrovani_mu/ishikawa_faktory.json"


class IshikawaFactorsService:
    def __init__(self) -> None:
        self._catalog: dict[str, dict] | None = None

    def reload(self) -> None:
        self._catalog = None

    def _load(self) -> dict[str, dict]:
        if self._catalog is not None:
            return self._catalog

        raw = self._read_json_file()
        if raw is None:
            self._catalog = deepcopy(ISHIKAWA_FALLBACK_CATALOG)
            return self._catalog

        normalized: dict[str, dict] = {}
        for category in ISHIKAWA_CATEGORIES:
            entry = raw.get(category)
            if not isinstance(entry, dict):
                normalized[category] = deepcopy(ISHIKAWA_FALLBACK_CATALOG[category])
                continue
            normalized[category] = self._normalize_entry(category, entry)

        self._catalog = normalized
        return self._catalog

    def _read_json_file(self) -> dict | None:
        if not _CATALOG_PATH.exists():
            return None

        try:
            data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict):
            return None
        return data

    def _normalize_entry(self, category: str, entry: dict) -> dict:
        fallback = ISHIKAWA_FALLBACK_CATALOG.get(category, ISHIKAWA_FALLBACK_CATALOG["Ostatní"])
        question = str(entry.get("question") or fallback["question"]).strip() or fallback["question"]

        raw_factors = entry.get("factors")
        factors: list[str] = []
        if isinstance(raw_factors, list):
            for item in raw_factors:
                value = str(item).strip()
                if value and value not in factors:
                    factors.append(value)

        factors = self._ensure_other_last(factors or list(fallback["factors"]))
        return {"question": question, "factors": factors}

    def _ensure_other_last(self, factors: list[str]) -> list[str]:
        without_other = [factor for factor in factors if factor != ISHIKAWA_OTHER_FACTOR]
        return [*without_other, ISHIKAWA_OTHER_FACTOR]

    def get_question(self, category: str) -> str:
        catalog = self._load()
        entry = catalog.get(category) or catalog.get("Ostatní")
        return entry["question"]

    def get_factors(self, category: str) -> tuple[str, ...]:
        catalog = self._load()
        entry = catalog.get(category) or catalog.get("Ostatní")
        return tuple(entry["factors"])

    def add_factor(self, category: str, factor: str) -> bool:
        value = factor.strip()
        if not value or value == ISHIKAWA_OTHER_FACTOR:
            return False

        catalog = deepcopy(self._load())
        if category not in catalog:
            category = "Ostatní"

        factors = list(catalog[category]["factors"])
        if value in factors:
            return True

        factors = [item for item in factors if item != ISHIKAWA_OTHER_FACTOR]
        factors.append(value)
        catalog[category]["factors"] = self._ensure_other_last(factors)

        try:
            _CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            _CATALOG_PATH.write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            return False

        self._catalog = catalog
        return True


ishikawa_factors_service = IshikawaFactorsService()
