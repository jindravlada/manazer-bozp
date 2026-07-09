from dataclasses import dataclass

from moduly.pravni_pozadavky.constants import process_code_sort_key
from moduly.pravni_pozadavky.repository.legal_change_repository import LegalChangeRepository
from moduly.pravni_pozadavky.repository.legal_change_section_repository import (
    LegalChangeSectionRepository,
)
from moduly.pravni_pozadavky.repository.legal_check_run_repository import LegalCheckRunRepository
from moduly.pravni_pozadavky.repository.legal_document_repository import LegalDocumentRepository
from moduly.pravni_pozadavky.repository.legal_document_version_repository import (
    LegalDocumentVersionRepository,
)
from moduly.pravni_pozadavky.repository.legal_requirement_repository import (
    LegalRequirementRepository,
)
from moduly.pravni_pozadavky.repository.legal_requirement_sanction_repository import (
    LegalRequirementSanctionRepository,
)
from moduly.pravni_pozadavky.repository.legal_requirement_source_repository import (
    LegalRequirementSourceRepository,
)
from moduly.pravni_pozadavky.repository.legal_section_repository import LegalSectionRepository


@dataclass(frozen=True)
class LegalRegistryDiagnosticStats:
    document_count: int
    version_count: int
    section_count: int
    requirement_count: int
    processes_without_sources_count: int
    source_count: int
    sanction_count: int
    check_run_count: int
    change_count: int
    change_section_count: int


@dataclass(frozen=True)
class LegalRegistryDiagnosticResult:
    stats: LegalRegistryDiagnosticStats
    issues: list[str]

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def is_consistent(self) -> bool:
        return not self.issues


class LegalRegistryDiagnosticService:
    def __init__(self):
        self.requirement_repository = LegalRequirementRepository()
        self.source_repository = LegalRequirementSourceRepository()
        self.sanction_repository = LegalRequirementSanctionRepository()
        self.document_repository = LegalDocumentRepository()
        self.version_repository = LegalDocumentVersionRepository()
        self.section_repository = LegalSectionRepository()
        self.check_run_repository = LegalCheckRunRepository()
        self.change_repository = LegalChangeRepository()
        self.change_section_repository = LegalChangeSectionRepository()

    def run(self) -> LegalRegistryDiagnosticResult:
        documents = self.document_repository.list_all(include_inactive=True)
        versions = self.version_repository.list_all(include_inactive=True)
        sections = self.section_repository.list_all()
        requirements = self.requirement_repository.get_all(active_only=None)
        sources = self.source_repository.list_all()
        sanctions = self.sanction_repository.list_all()
        check_runs = self.check_run_repository.list_all(include_inactive=True)
        changes = self.change_repository.list_all(include_inactive=True)
        change_sections = self.change_section_repository.list_all()

        document_ids = {document.id for document in documents}
        version_ids = {version.id for version in versions}
        section_ids = {section.id for section in sections}
        requirement_ids = {requirement.id for requirement in requirements}
        check_run_ids = {check_run.id for check_run in check_runs}
        change_ids = {change.id for change in changes}

        sources_by_requirement: dict[int, list] = {}
        for source in sources:
            sources_by_requirement.setdefault(source.requirement_id, []).append(source)

        issues: list[str] = []

        for requirement in sorted(requirements, key=process_code_sort_key):
            if not sources_by_requirement.get(requirement.id):
                process_label = requirement.process_code.strip() or f"ID {requirement.id}"
                issues.append(f"Proces {process_label} nemá žádný právní podklad.")

        for source in sources:
            if source.requirement_id not in requirement_ids:
                issues.append(
                    f"Právní podklad ID {source.id} odkazuje na neexistující proces.",
                )
            if source.legal_section_id not in section_ids:
                issues.append(
                    f"Právní podklad ID {source.id} odkazuje na neexistující ustanovení.",
                )

        for section in sections:
            if section.legal_document_version_id not in version_ids:
                issues.append(
                    f"Ustanovení ID {section.id} odkazuje na neexistující verzi předpisu.",
                )

        for version in versions:
            if version.legal_document_id not in document_ids:
                issues.append(
                    f"Verze předpisu ID {version.id} odkazuje na neexistující právní předpis.",
                )

        for change in changes:
            if (
                change.legal_check_run_id is not None
                and change.legal_check_run_id not in check_run_ids
            ):
                issues.append(
                    f"Změna ID {change.id} odkazuje na neexistující kontrolu změn.",
                )

        for change_section in change_sections:
            if change_section.legal_change_id not in change_ids:
                issues.append(
                    f"Změněné ustanovení ID {change_section.id} odkazuje na neexistující změnu.",
                )

        processes_without_sources_count = sum(
            1 for requirement in requirements if not sources_by_requirement.get(requirement.id)
        )

        stats = LegalRegistryDiagnosticStats(
            document_count=len(documents),
            version_count=len(versions),
            section_count=len(sections),
            requirement_count=len(requirements),
            processes_without_sources_count=processes_without_sources_count,
            source_count=len(sources),
            sanction_count=len(sanctions),
            check_run_count=len(check_runs),
            change_count=len(changes),
            change_section_count=len(change_sections),
        )
        return LegalRegistryDiagnosticResult(stats=stats, issues=issues)

    def format_report(self, result: LegalRegistryDiagnosticResult) -> str:
        lines = [
            self._stat_line("Právní předpisy", result.stats.document_count),
            self._stat_line("Verze předpisů", result.stats.version_count),
            self._stat_line("Ustanovení", result.stats.section_count),
            "",
            self._stat_line("Řídicí procesy", result.stats.requirement_count),
            self._stat_line(
                "Procesy bez podkladů",
                result.stats.processes_without_sources_count,
            ),
            self._stat_line("Právní podklady", result.stats.source_count),
            "",
            self._stat_line("Sankce", result.stats.sanction_count),
            "",
            self._stat_line("Kontroly změn", result.stats.check_run_count),
            self._stat_line("Zjištěné změny", result.stats.change_count),
            self._stat_line("Změněná ustanovení", result.stats.change_section_count),
            "",
        ]

        if result.is_consistent:
            lines.append("✔ Registr je konzistentní.")
        else:
            lines.append(f"⚠ Bylo nalezeno {result.issue_count} problémů.")
            lines.append("")
            lines.extend(f"- {issue}" for issue in result.issues)

        return "\n".join(lines)

    def _stat_line(self, label: str, value: int) -> str:
        width = 30
        filler = "." * max(3, width - len(label) - len(str(value)) - 1)
        return f"{label} {filler} {value}"


legal_registry_diagnostic_service = LegalRegistryDiagnosticService()
