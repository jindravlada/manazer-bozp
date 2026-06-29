from core.modules.module_definition import ModuleDefinition
from moduly.kontroly.ui.kontroly_page import KontrolyPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key="kontroly",
        name="Kontroly",
        description="Evidence kontrol BOZP na pracovištích.",
        page_factory=KontrolyPage,
        enabled=True,
    )
