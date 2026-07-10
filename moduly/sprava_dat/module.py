from core.modules.module_definition import ModuleDefinition
from moduly.sprava_dat.ui.sprava_dat_page import SpravaDatPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key="sprava_dat",
        name="Správa dat",
        description="Servisní správa záloh, přenosu dat a diagnostiky.",
        page_factory=SpravaDatPage,
        enabled=True,
    )
