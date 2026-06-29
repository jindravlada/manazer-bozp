from core.modules.module_definition import ModuleDefinition
from moduly.vysetrovani_mu.ui.vysetrovani_mu_page import VysetrovaniMuPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key="vysetrovani_mu",
        name="Vyšetřování MU",
        description="Proces vyšetřování mimořádných událostí.",
        page_factory=VysetrovaniMuPage,
        enabled=True,
    )
