from core.modules.module_definition import ModuleDefinition
from moduly.audity.ui.audity_page import AudityPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key="audity",
        name="Audity",
        description="Evidence interních auditů IMS.",
        page_factory=AudityPage,
        enabled=True,
    )
