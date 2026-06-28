from core.modules.module_definition import ModuleDefinition
from moduly.nastaveni.ui.nastaveni_page import NastaveniPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key="nastaveni",
        name="Nastavení",
        description="Společná nastavení a globální číselníky systému.",
        page_factory=NastaveniPage,
        enabled=True,
    )
