from core.modules.module_definition import ModuleDefinition
from moduly.ukoly.ui.ukoly_page import UkolyPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key="ukoly",
        name="Úkoly",
        description="Evidence úkolů, termínů a odpovědných osob.",
        page_factory=UkolyPage,
        enabled=True,
    )
