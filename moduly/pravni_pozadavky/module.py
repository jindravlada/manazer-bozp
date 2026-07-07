from core.modules.module_definition import ModuleDefinition
from moduly.pravni_pozadavky.ui.pravni_pozadavky_page import PravniPozadavkyPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key="pravni_pozadavky",
        name="Právní požadavky",
        description="Registr právních požadavků, plnění a odpovědností.",
        page_factory=PravniPozadavkyPage,
        enabled=True,
    )
