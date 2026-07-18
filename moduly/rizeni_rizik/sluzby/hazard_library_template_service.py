from dataclasses import dataclass
from datetime import datetime

from core.utils.czech_sort import czech_sorted
from moduly.nastaveni.constants.workplace_hierarchy_constants import (
    WORKPLACE_ITEM_TYPE_OPERATION,
)
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.rizeni_rizik.constants import (
    HAZARD_INVENTORY_CATEGORIES,
    HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
)
from moduly.rizeni_rizik.constants_library import (
    DEFAULT_HAZARD_LIBRARY_SCOPE,
    DEFAULT_HAZARD_LIBRARY_VERSION,
    HAZARD_LIBRARY_REVISION_REASON_MANUAL,
    HAZARD_LIBRARY_SCOPE_ALL,
    HAZARD_LIBRARY_SCOPE_LABELS,
    HAZARD_LIBRARY_SCOPE_MANUAL,
    HAZARD_LIBRARY_SCOPE_SELECTED,
    HAZARD_LIBRARY_SCOPES,
)
from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
from moduly.rizeni_rizik.repository.hazard_library_template_repository import (
    HazardLibraryTemplateOperationRepository,
    HazardLibraryTemplateRepository,
)


class HazardLibraryTemplateError(ValueError):
    pass


@dataclass
class HazardLibraryTemplateRow:
    template: HazardLibraryTemplate
    scope_label: str
    operation_count_label: str


@dataclass
class HazardLibraryScopeChangePreview:
    """Náhled změny rozsahu – vyžaduje potvrzení uživatele."""

    removed_operation_names: list[str]


def normalize_template_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


class HazardLibraryTemplateService:
    def __init__(self):
        self.repository = HazardLibraryTemplateRepository()
        self.operation_repository = HazardLibraryTemplateOperationRepository()

    def get_all_rows(self, *, include_inactive: bool = True) -> list[HazardLibraryTemplateRow]:
        templates = self.repository.get_all(include_inactive=include_inactive)
        counts = self.operation_repository.get_counts_by_templates(
            [template.id for template in templates],
        )
        rows = [
            self._to_row(template, counts.get(template.id, 0))
            for template in templates
        ]
        return czech_sorted(rows, key=lambda row: row.template.name.casefold())

    def get_by_id(self, template_id: int | None) -> HazardLibraryTemplate | None:
        if not template_id:
            return None
        return self.repository.get_by_id(template_id)

    def get_operation_ids(self, template_id: int) -> list[int]:
        return self.operation_repository.get_operation_ids(template_id)

    def get_active_operations(self) -> list:
        workplaces = settings_service.get_workplaces(include_inactive=False)
        operations = [
            workplace
            for workplace in workplaces
            if workplace.item_type == WORKPLACE_ITEM_TYPE_OPERATION
        ]
        return czech_sorted(operations, key=lambda item: item.name)

    def preview_scope_change(
        self,
        template_id: int | None,
        *,
        new_scope: str,
        operation_ids: list[int],
    ) -> HazardLibraryScopeChangePreview | None:
        current_scope = DEFAULT_HAZARD_LIBRARY_SCOPE
        current_operation_ids: list[int] = []
        if template_id is not None:
            template = self.repository.get_by_id(template_id)
            if template is not None:
                current_scope = template.application_scope
                current_operation_ids = self.get_operation_ids(template_id)

        if new_scope == current_scope and new_scope != HAZARD_LIBRARY_SCOPE_SELECTED:
            if new_scope in {HAZARD_LIBRARY_SCOPE_ALL, HAZARD_LIBRARY_SCOPE_MANUAL}:
                if current_operation_ids:
                    return HazardLibraryScopeChangePreview(
                        removed_operation_names=self._operation_names(current_operation_ids),
                    )
            return None

        if new_scope == HAZARD_LIBRARY_SCOPE_SELECTED:
            return None

        if not current_operation_ids:
            return None

        if new_scope in {HAZARD_LIBRARY_SCOPE_ALL, HAZARD_LIBRARY_SCOPE_MANUAL}:
            return HazardLibraryScopeChangePreview(
                removed_operation_names=self._operation_names(current_operation_ids),
            )

        if new_scope == HAZARD_LIBRARY_SCOPE_SELECTED and current_scope != new_scope:
            removed = [
                operation_id
                for operation_id in current_operation_ids
                if operation_id not in set(operation_ids)
            ]
            if removed:
                return HazardLibraryScopeChangePreview(
                    removed_operation_names=self._operation_names(removed),
                )
        return None

    def find_active_by_name(self, name: str) -> HazardLibraryTemplate | None:
        normalized = normalize_template_name(name)
        if not normalized:
            return None
        for template in self.repository.get_all(include_inactive=False):
            if normalize_template_name(template.name) == normalized:
                return template
        return None

    def create_template(
        self,
        *,
        name: str,
        category: str = HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        description: str = "",
        application_scope: str = DEFAULT_HAZARD_LIBRARY_SCOPE,
        version_number: int = DEFAULT_HAZARD_LIBRARY_VERSION,
        note: str = "",
        active: bool = True,
        operation_ids: list[int] | None = None,
        allow_duplicate_name: bool = False,
    ) -> HazardLibraryTemplate:
        normalized_name = self._validate_name(name)
        validated_category = self._validate_category(category)
        scope = self._validate_scope(application_scope)
        version = self._validate_version(version_number)
        if active and not allow_duplicate_name:
            self._ensure_unique_active_name(normalized_name)

        validated_operation_ids = self._validate_operation_ids(
            scope,
            operation_ids or [],
        )

        template = HazardLibraryTemplate(
            name=normalized_name,
            category=validated_category,
            description=description.strip(),
            application_scope=scope,
            version_number=version,
            note=note.strip(),
            active=active,
        )
        saved = self.repository.add(template)
        self._apply_operations(saved.id, scope, validated_operation_ids)
        return saved

    def update_template(
        self,
        template_id: int,
        *,
        name: str,
        category: str = HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        description: str = "",
        application_scope: str = DEFAULT_HAZARD_LIBRARY_SCOPE,
        version_number: int = DEFAULT_HAZARD_LIBRARY_VERSION,
        note: str = "",
        active: bool = True,
        operation_ids: list[int] | None = None,
    ) -> HazardLibraryTemplate | None:
        template = self.repository.get_by_id(template_id)
        if template is None:
            return None

        normalized_name = self._validate_name(name)
        validated_category = self._validate_category(category)
        scope = self._validate_scope(application_scope)
        version = self._validate_version(version_number)
        if active:
            self._ensure_unique_active_name(normalized_name, exclude_template_id=template_id)

        validated_operation_ids = self._validate_operation_ids(
            scope,
            operation_ids or [],
        )

        template.name = normalized_name
        template.category = validated_category
        template.description = description.strip()
        template.application_scope = scope
        template.version_number = version
        template.note = note.strip()
        template.active = active
        template.updated_at = datetime.now()
        saved = self.repository.update(template)
        self._apply_operations(saved.id, scope, validated_operation_ids)
        return saved

    def activate(self, template_id: int) -> bool:
        template = self.repository.get_by_id(template_id)
        if template is None:
            return False
        self._ensure_unique_active_name(template.name, exclude_template_id=template_id)
        return self.repository.activate(template_id)

    def deactivate(self, template_id: int) -> bool:
        return self.repository.deactivate(template_id)

    def bump_content_version(
        self,
        template_id: int,
        *,
        change_reason: str = HAZARD_LIBRARY_REVISION_REASON_MANUAL,
    ) -> HazardLibraryTemplate | None:
        template = self.repository.get_by_id(template_id)
        if template is None:
            return None
        template.version_number += 1
        template.updated_at = datetime.now()
        updated = self.repository.update(template)
        from moduly.rizeni_rizik.sluzby.hazard_library_template_revision_service import (
            hazard_library_template_revision_service,
        )

        hazard_library_template_revision_service.record_revision(
            updated.id,
            revision_number=updated.version_number,
            change_reason=change_reason,
        )
        return updated

    def is_template_content_editable(self, template_id: int) -> bool:
        template = self.repository.get_by_id(template_id)
        return template is not None and template.active

    def format_scope_label(self, scope: str) -> str:
        return HAZARD_LIBRARY_SCOPE_LABELS.get(scope, scope)

    def format_operation_count_label(
        self,
        template: HazardLibraryTemplate,
        *,
        selected_count: int,
    ) -> str:
        if template.application_scope == HAZARD_LIBRARY_SCOPE_ALL:
            return "Všechny"
        if template.application_scope == HAZARD_LIBRARY_SCOPE_MANUAL:
            return "—"
        return str(selected_count)

    def _to_row(
        self,
        template: HazardLibraryTemplate,
        selected_count: int,
    ) -> HazardLibraryTemplateRow:
        return HazardLibraryTemplateRow(
            template=template,
            scope_label=self.format_scope_label(template.application_scope),
            operation_count_label=self.format_operation_count_label(
                template,
                selected_count=selected_count,
            ),
        )

    def _apply_operations(
        self,
        template_id: int,
        scope: str,
        operation_ids: list[int],
    ) -> None:
        if scope == HAZARD_LIBRARY_SCOPE_SELECTED:
            self.operation_repository.replace_operations(template_id, operation_ids)
            return
        self.operation_repository.clear_operations(template_id)

    def _validate_name(self, name: str) -> str:
        normalized = " ".join(name.strip().split())
        if not normalized:
            raise HazardLibraryTemplateError("Název zdroje rizika je povinný.")
        return normalized

    def _validate_category(self, category: str) -> str:
        if category not in HAZARD_INVENTORY_CATEGORIES:
            raise HazardLibraryTemplateError("Neplatná kategorie zdroje rizika.")
        return category

    def _validate_scope(self, scope: str) -> str:
        if scope not in HAZARD_LIBRARY_SCOPES:
            raise HazardLibraryTemplateError("Neplatný rozsah použití vzoru.")
        return scope

    def _validate_version(self, version_number: int) -> int:
        if not isinstance(version_number, int) or version_number < 1:
            raise HazardLibraryTemplateError("Revize musí být kladné celé číslo.")
        return version_number

    def _validate_operation_ids(
        self,
        scope: str,
        operation_ids: list[int],
    ) -> list[int]:
        if scope in {HAZARD_LIBRARY_SCOPE_ALL, HAZARD_LIBRARY_SCOPE_MANUAL}:
            if operation_ids:
                raise HazardLibraryTemplateError(
                    "U zvoleného rozsahu nelze ukládat vazby na jednotlivé provozy."
                )
            return []

        if scope == HAZARD_LIBRARY_SCOPE_SELECTED:
            if not operation_ids:
                raise HazardLibraryTemplateError(
                    "U rozsahu Vybrané provozy vyberte alespoň jeden provoz."
                )
            validated: list[int] = []
            for operation_id in sorted(set(operation_ids)):
                workplace = settings_service.get_workplace_by_id(operation_id)
                if workplace is None:
                    raise HazardLibraryTemplateError("Vybraný provoz neexistuje.")
                if not workplace.active:
                    raise HazardLibraryTemplateError(
                        f"Provoz „{workplace.name}“ není aktivní."
                    )
                if workplace.item_type != WORKPLACE_ITEM_TYPE_OPERATION:
                    raise HazardLibraryTemplateError(
                        f"„{workplace.name}“ není položka typu Provoz."
                    )
                validated.append(workplace.id)
            return validated

        return []

    def _ensure_unique_active_name(
        self,
        name: str,
        *,
        exclude_template_id: int | None = None,
    ) -> None:
        normalized = normalize_template_name(name)
        for template in self.repository.get_all(include_inactive=False):
            if template.id == exclude_template_id:
                continue
            if normalize_template_name(template.name) == normalized:
                raise HazardLibraryTemplateError(
                    f"Aktivní zdroj rizika „{template.name}“ již existuje."
                )

    def _operation_names(self, operation_ids: list[int]) -> list[str]:
        names: list[str] = []
        for operation_id in operation_ids:
            workplace = settings_service.get_workplace_by_id(operation_id)
            if workplace is not None:
                names.append(workplace.name)
        return names


hazard_library_template_service = HazardLibraryTemplateService()
