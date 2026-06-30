import json
from copy import deepcopy
from pathlib import Path

from core.services.editable_catalog_service import editable_catalog_service
from moduly.vysetrovani_mu.constants import (
    ISHIKAWA_CATEGORIES,
    ISHIKAWA_FALLBACK_CATALOG,
    ISHIKAWA_OTHER_FACTOR,
)

_CATALOG_RELATIVE_PATH = "modulove/vysetrovani_mu/ishikawa_faktory.json"


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

    def _catalog_path(self) -> Path:
        from core.services.storage_service import storage_service

        return editable_catalog_service.ensure_catalog(
            storage_service.ciselniky_dir,
            _CATALOG_RELATIVE_PATH,
        )

    def _read_json_file(self) -> dict | None:
        catalog_path = self._catalog_path()
        if not catalog_path.exists():
            return None

        try:
            data = json.loads(catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict):
            return None
        return data

    def _read_bundled_json(self) -> dict | None:
        bundled_path = editable_catalog_service.bundled_path(_CATALOG_RELATIVE_PATH)
        if not bundled_path.exists():
            return None

        try:
            data = json.loads(bundled_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict):
            return None
        return data

    def _bundled_factors_by_name(self, category: str) -> dict[str, dict]:
        raw = self._read_bundled_json()
        if raw is None:
            return {}

        entry = raw.get(category)
        if not isinstance(entry, dict):
            return {}

        factors = entry.get("factors")
        if not isinstance(factors, list):
            return {}

        return {
            str(item.get("name") or "").strip(): deepcopy(item)
            for item in factors
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        }

    def _fallback_entry(self, category: str) -> dict:
        return ISHIKAWA_FALLBACK_CATALOG.get(category, ISHIKAWA_FALLBACK_CATALOG["Ostatní"])

    def _fallback_factors(self, category: str) -> list[dict]:
        return deepcopy(self._fallback_entry(category)["factors"])

    def _fallback_factors_by_name(self, category: str) -> dict[str, dict]:
        return {
            factor["name"]: deepcopy(factor)
            for factor in self._fallback_factors(category)
        }

    def _normalize_string_list(self, raw_items) -> list[str]:
        if not isinstance(raw_items, list):
            return []

        values: list[str] = []
        for item in raw_items:
            value = str(item).strip()
            if value and value not in values:
                values.append(value)
        return values

    def _normalize_questions(self, raw_questions) -> list[str]:
        return self._normalize_string_list(raw_questions)

    def _normalize_evidence(self, raw_evidence) -> list[str]:
        return self._normalize_string_list(raw_evidence)

    def _normalize_related(self, raw_related) -> list[str]:
        return self._normalize_string_list(raw_related)

    def _normalize_suggest(self, raw_suggest) -> list[dict]:
        if not isinstance(raw_suggest, list):
            return []

        values: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for item in raw_suggest:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category") or "").strip()
            factor = str(item.get("factor") or "").strip()
            if not category or not factor:
                continue
            key = (category, factor)
            if key in seen:
                continue
            seen.add(key)
            values.append({"category": category, "factor": factor})
        return values

    def _resolve_suggest_field(
        self,
        item: dict,
        fallback: dict,
        bundled: dict | None = None,
    ) -> list[dict]:
        values = self._normalize_suggest(item.get("suggest"))
        if values:
            return values

        for source in (bundled, fallback):
            if not source:
                continue
            source_values = self._normalize_suggest(source.get("suggest"))
            if source_values:
                return source_values
        return []

    @staticmethod
    def format_suggest_line(category: str, factor: str) -> str:
        return f"→ {category} → {factor}"

    def _normalize_parent(self, raw_parent, name: str, valid_names: set[str]) -> str:
        parent = str(raw_parent or "").strip()
        if not parent or parent == name or parent == ISHIKAWA_OTHER_FACTOR:
            return ""
        if parent not in valid_names:
            return ""
        return parent

    def _build_factor_dict(
        self,
        name: str,
        questions: list[str],
        evidence: list[str],
        related: list[str],
        parent: str = "",
        supports: list[str] | None = None,
        contradicts: list[str] | None = None,
        actions: list[str] | None = None,
        suggest: list[dict] | None = None,
    ) -> dict:
        return {
            "name": name,
            "questions": questions,
            "evidence": evidence,
            "related": related,
            "parent": parent,
            "supports": list(supports or []),
            "contradicts": list(contradicts or []),
            "actions": list(actions or []),
            "suggest": deepcopy(suggest or []),
        }

    def _resolve_string_list_field(
        self,
        item: dict,
        fallback: dict,
        field: str,
        bundled: dict | None = None,
    ) -> list[str]:
        values = self._normalize_string_list(item.get(field))
        if values:
            return values

        for source in (bundled, fallback):
            if not source:
                continue
            source_values = self._normalize_string_list(source.get(field))
            if source_values:
                return source_values
        return []

    @staticmethod
    def _match_key(value: str) -> str:
        return "".join(ch for ch in value.strip().lower() if ch.isalnum() or ch.isspace()).strip()

    def _value_matches_seed(self, value: str, seed_values: list[str]) -> bool:
        if value in seed_values:
            return True

        value_key = self._match_key(value)
        if not value_key:
            return True

        for seed_value in seed_values:
            seed_key = self._match_key(seed_value)
            if not seed_key:
                continue
            if value_key == seed_key or value_key in seed_key or seed_key in value_key:
                return True

            value_tokens = {token for token in value_key.split() if len(token) >= 5}
            seed_tokens = {token for token in seed_key.split() if len(token) >= 5}
            if value_tokens & seed_tokens:
                return True
        return False

    def _user_only_has_seed_content(self, user_values: list[str], seed_values: list[str]) -> bool:
        if not user_values:
            return True
        if not seed_values:
            return False
        return all(self._value_matches_seed(value, seed_values) for value in user_values)

    def _resolve_seed_string_list_field(
        self,
        item: dict,
        fallback: dict,
        field: str,
        bundled: dict | None = None,
    ) -> list[str]:
        user_values = self._normalize_string_list(item.get(field))
        for source in (bundled, fallback):
            if not source:
                continue
            seed_values = self._normalize_string_list(source.get(field))
            if not user_values:
                if seed_values:
                    return seed_values
                continue
            if (
                seed_values
                and len(seed_values) >= len(user_values)
                and self._user_only_has_seed_content(user_values, seed_values)
            ):
                return seed_values
        return user_values

    def _normalize_factor_item(
        self,
        item,
        fallback_by_name: dict[str, dict],
        bundled_by_name: dict[str, dict],
        valid_names: set[str],
    ) -> dict | None:
        if isinstance(item, str):
            name = item.strip()
            if not name:
                return None
            fallback = fallback_by_name.get(
                name,
                {
                    "name": name,
                    "questions": [],
                    "evidence": [],
                    "related": [],
                    "parent": "",
                    "supports": [],
                    "contradicts": [],
                    "actions": [],
                    "suggest": [],
                },
            )
            parent = self._normalize_parent(fallback.get("parent"), name, valid_names)
            return self._build_factor_dict(
                name,
                self._normalize_questions(fallback.get("questions")),
                self._normalize_evidence(fallback.get("evidence")),
                self._normalize_related(fallback.get("related")),
                parent,
                self._normalize_string_list(fallback.get("supports")),
                self._normalize_string_list(fallback.get("contradicts")),
                self._normalize_string_list(fallback.get("actions")),
                self._normalize_suggest(fallback.get("suggest")),
            )

        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if not name:
                return None
            fallback = fallback_by_name.get(name, {})
            bundled = bundled_by_name.get(name, {})
            questions = self._resolve_seed_string_list_field(
                item,
                fallback,
                "questions",
                bundled,
            )
            evidence = self._resolve_seed_string_list_field(
                item,
                fallback,
                "evidence",
                bundled,
            )
            related = self._resolve_string_list_field(item, fallback, "related", bundled)

            if "parent" in item:
                parent = self._normalize_parent(item.get("parent"), name, valid_names)
            elif bundled.get("parent"):
                parent = self._normalize_parent(bundled.get("parent"), name, valid_names)
            else:
                parent = self._normalize_parent(fallback.get("parent"), name, valid_names)

            return self._build_factor_dict(
                name,
                questions,
                evidence,
                related,
                parent,
                self._resolve_string_list_field(item, fallback, "supports", bundled),
                self._resolve_string_list_field(item, fallback, "contradicts", bundled),
                self._resolve_string_list_field(item, fallback, "actions", bundled),
                self._resolve_suggest_field(item, fallback, bundled),
            )

        return None

    def _normalize_factors_list(self, category: str, raw_factors) -> list[dict]:
        fallback_factors = self._fallback_factors(category)
        fallback_by_name = self._fallback_factors_by_name(category)
        bundled_by_name = self._bundled_factors_by_name(category)

        source = raw_factors if isinstance(raw_factors, list) and raw_factors else fallback_factors
        raw_names = {
            str(item.get("name") if isinstance(item, dict) else item).strip()
            for item in source
        }
        raw_names.discard("")
        valid_names = raw_names or {factor["name"] for factor in fallback_factors}

        factors: list[dict] = []
        seen: set[str] = set()

        for item in source:
            normalized = self._normalize_factor_item(
                item,
                fallback_by_name,
                bundled_by_name,
                valid_names,
            )
            if normalized is None or normalized["name"] in seen:
                continue
            seen.add(normalized["name"])
            factors.append(normalized)

        if not factors:
            factors = fallback_factors

        valid_names = {factor["name"] for factor in factors}
        normalized_factors = []
        for factor in factors:
            normalized_factors.append(
                self._build_factor_dict(
                    factor["name"],
                    self._normalize_questions(factor.get("questions")),
                    self._normalize_evidence(factor.get("evidence")),
                    self._normalize_related(factor.get("related")),
                    self._normalize_parent(factor.get("parent"), factor["name"], valid_names),
                    self._normalize_string_list(factor.get("supports")),
                    self._normalize_string_list(factor.get("contradicts")),
                    self._normalize_string_list(factor.get("actions")),
                    self._normalize_suggest(factor.get("suggest")),
                )
            )

        return self._ensure_other_last(normalized_factors)

    def _normalize_entry(self, category: str, entry: dict) -> dict:
        fallback = self._fallback_entry(category)
        question = str(entry.get("question") or fallback["question"]).strip() or fallback["question"]
        factors = self._normalize_factors_list(category, entry.get("factors"))
        return {"question": question, "factors": factors}

    def _effective_parent(self, factor: dict, valid_names: set[str]) -> str:
        return self._normalize_parent(factor.get("parent"), factor.get("name") or "", valid_names)

    def _ensure_other_last(self, factors: list[dict]) -> list[dict]:
        without_other = [factor for factor in factors if factor.get("name") != ISHIKAWA_OTHER_FACTOR]
        other = next(
            (factor for factor in factors if factor.get("name") == ISHIKAWA_OTHER_FACTOR),
            {"name": ISHIKAWA_OTHER_FACTOR, "questions": [], "evidence": [], "related": [], "parent": "", "supports": [], "contradicts": [], "actions": [], "suggest": []},
        )
        return [
            *without_other,
            self._build_factor_dict(
                other["name"],
                self._normalize_questions(other.get("questions")),
                self._normalize_evidence(other.get("evidence")),
                self._normalize_related(other.get("related")),
                "",
                self._normalize_string_list(other.get("supports")),
                self._normalize_string_list(other.get("contradicts")),
                self._normalize_string_list(other.get("actions")),
                self._normalize_suggest(other.get("suggest")),
            ),
        ]

    def get_question(self, category: str) -> str:
        catalog = self._load()
        entry = catalog.get(category) or catalog.get("Ostatní")
        return entry["question"]

    def _category_factors(self, category: str) -> list[dict]:
        catalog = self._load()
        entry = catalog.get(category) or catalog.get("Ostatní")
        return list(entry["factors"])

    def get_factors(self, category: str) -> tuple[str, ...]:
        return tuple(factor["name"] for factor in self._category_factors(category))

    def get_child_factors(self, category: str, parent_name: str) -> tuple[str, ...]:
        parent = parent_name.strip()
        if not parent:
            return ()

        factors = self._category_factors(category)
        valid_names = {factor["name"] for factor in factors}
        return tuple(
            factor["name"]
            for factor in factors
            if self._effective_parent(factor, valid_names) == parent
        )

    def get_expanded_parents(self, category: str, selected_factor: str) -> frozenset[str]:
        selected = selected_factor.strip()
        if not selected or selected == ISHIKAWA_OTHER_FACTOR:
            return frozenset()

        if self.get_factor(category, selected) is None:
            return frozenset()

        valid_names = set(self.get_factors(category))
        expanded: set[str] = set()
        current = selected
        while True:
            factor = self.get_factor(category, current)
            if factor is None:
                break
            parent = self._effective_parent(factor, valid_names)
            if not parent:
                break
            expanded.add(parent)
            current = parent

        if self.get_child_factors(category, selected):
            expanded.add(selected)

        return frozenset(expanded)

    def get_expanded_parent(self, category: str, selected_factor: str) -> str | None:
        expanded = self.get_expanded_parents(category, selected_factor)
        if not expanded:
            return None
        factors = self._category_factors(category)
        valid_names = {factor["name"] for factor in factors}
        for factor in factors:
            name = factor["name"]
            if name in expanded and not self._effective_parent(factor, valid_names):
                return name
        return next(iter(expanded), None)

    def get_factors_display(
        self,
        category: str,
        expanded_parent: str | None = None,
        *,
        expanded_parents: frozenset[str] | set[str] | None = None,
    ) -> tuple[tuple[str, int], ...]:
        factors = self._category_factors(category)
        valid_names = {factor["name"] for factor in factors}
        children_by_parent: dict[str, list[str]] = {}
        main_factors: list[str] = []

        for factor in factors:
            name = factor["name"]
            parent = self._effective_parent(factor, valid_names)
            if parent:
                children_by_parent.setdefault(parent, []).append(name)
            elif name != ISHIKAWA_OTHER_FACTOR:
                main_factors.append(name)

        expanded = set(expanded_parents or ())
        if expanded_parent:
            expanded.add(expanded_parent)

        display: list[tuple[str, int]] = []

        def append_tree(name: str, level: int) -> None:
            display.append((name, level))
            if name in expanded:
                for child in children_by_parent.get(name, []):
                    append_tree(child, level + 1)

        for name in main_factors:
            append_tree(name, 0)

        if any(factor["name"] == ISHIKAWA_OTHER_FACTOR for factor in factors):
            display.append((ISHIKAWA_OTHER_FACTOR, 0))

        return tuple(display)

    def get_main_factors(self, category: str, *, exclude: str = "") -> tuple[str, ...]:
        factors = self._category_factors(category)
        valid_names = {factor["name"] for factor in factors}
        result: list[str] = []
        for factor in factors:
            name = factor["name"]
            if name == exclude or name == ISHIKAWA_OTHER_FACTOR:
                continue
            if not self._effective_parent(factor, valid_names):
                result.append(name)
        return tuple(result)

    def get_factor_questions(self, category: str, factor_name: str) -> tuple[str, ...]:
        name = factor_name.strip()
        if not name:
            return ()

        for factor in self._category_factors(category):
            if factor.get("name") == name:
                return tuple(factor.get("questions") or ())
        return ()

    def get_factor_evidence(self, category: str, factor_name: str) -> tuple[str, ...]:
        name = factor_name.strip()
        if not name:
            return ()

        for factor in self._category_factors(category):
            if factor.get("name") == name:
                return tuple(factor.get("evidence") or ())
        return ()

    def get_factor_related(self, category: str, factor_name: str) -> tuple[str, ...]:
        name = factor_name.strip()
        if not name:
            return ()

        category_factors = set(self.get_factors(category))
        for factor in self._category_factors(category):
            if factor.get("name") == name:
                related = self._normalize_related(factor.get("related"))
                return tuple(item for item in related if item in category_factors)
        return ()

    def get_factor_supports(self, category: str, factor_name: str) -> tuple[str, ...]:
        name = factor_name.strip()
        if not name:
            return ()

        for factor in self._category_factors(category):
            if factor.get("name") == name:
                return tuple(factor.get("supports") or ())
        return ()

    def get_factor_contradicts(self, category: str, factor_name: str) -> tuple[str, ...]:
        name = factor_name.strip()
        if not name:
            return ()

        for factor in self._category_factors(category):
            if factor.get("name") == name:
                return tuple(factor.get("contradicts") or ())
        return ()

    def get_factor_actions(self, category: str, factor_name: str) -> tuple[str, ...]:
        name = factor_name.strip()
        if not name:
            return ()

        for factor in self._category_factors(category):
            if factor.get("name") == name:
                return tuple(factor.get("actions") or ())
        return ()

    def get_factor_suggest(self, category: str, factor_name: str) -> tuple[dict, ...]:
        name = factor_name.strip()
        if not name:
            return ()

        for factor in self._category_factors(category):
            if factor.get("name") == name:
                return tuple(deepcopy(item) for item in self._normalize_suggest(factor.get("suggest")))
        return ()

    def get_factor(self, category: str, factor_name: str) -> dict | None:
        name = factor_name.strip()
        if not name:
            return None

        for factor in self._category_factors(category):
            if factor.get("name") == name:
                return deepcopy(factor)
        return None

    def _save_catalog(self, catalog: dict) -> bool:
        try:
            catalog_path = self._catalog_path()
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            return False

        self._catalog = catalog
        return True

    def update_factor(
        self,
        category: str,
        original_name: str,
        name: str,
        questions: list[str],
        evidence: list[str],
        related: list[str],
        parent: str = "",
        supports: list[str] | None = None,
        contradicts: list[str] | None = None,
        actions: list[str] | None = None,
        suggest: list[dict] | None = None,
    ) -> bool:
        original = original_name.strip()
        new_name = name.strip()
        new_parent = parent.strip()
        if not original or not new_name:
            return False
        if new_name == ISHIKAWA_OTHER_FACTOR and original != ISHIKAWA_OTHER_FACTOR:
            return False
        if new_parent == ISHIKAWA_OTHER_FACTOR or new_parent == new_name:
            new_parent = ""

        catalog = deepcopy(self._load())
        if category not in catalog:
            category = "Ostatní"

        factors = list(catalog[category]["factors"])
        index = next((idx for idx, item in enumerate(factors) if item.get("name") == original), None)
        if index is None:
            return False

        if new_name != original and any(item.get("name") == new_name for item in factors):
            return False

        valid_names = {item.get("name") for item in factors if item.get("name")}
        if new_parent and new_parent not in valid_names:
            new_parent = ""

        normalized_related = [
            item
            for item in self._normalize_related(related)
            if item in valid_names and item != new_name
        ]

        if new_name != original:
            for item in factors:
                if item.get("parent") == original:
                    item["parent"] = new_name

        factors[index] = self._build_factor_dict(
            new_name,
            self._normalize_questions(questions),
            self._normalize_evidence(evidence),
            normalized_related,
            new_parent if new_name != ISHIKAWA_OTHER_FACTOR else "",
            self._normalize_string_list(supports),
            self._normalize_string_list(contradicts),
            self._normalize_string_list(actions),
            self._normalize_suggest(suggest),
        )
        catalog[category]["factors"] = self._ensure_other_last(factors)
        return self._save_catalog(catalog)

    def add_factor(self, category: str, factor: str) -> bool:
        value = factor.strip()
        if not value or value == ISHIKAWA_OTHER_FACTOR:
            return False

        catalog = deepcopy(self._load())
        if category not in catalog:
            category = "Ostatní"

        factors = list(catalog[category]["factors"])
        if any(item.get("name") == value for item in factors):
            return True

        factors = [item for item in factors if item.get("name") != ISHIKAWA_OTHER_FACTOR]
        factors.append(
            {
                "name": value,
                "questions": [],
                "evidence": [],
                "related": [],
                "parent": "",
                "supports": [],
                "contradicts": [],
                "actions": [],
                "suggest": [],
            }
        )
        catalog[category]["factors"] = self._ensure_other_last(factors)

        return self._save_catalog(catalog)


ishikawa_factors_service = IshikawaFactorsService()
