from core.modules.module_definition import ModuleDefinition
from moduly.dashboard.ui.dashboard_page import DashboardPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key="dashboard",
        name="Dashboard",
        description="Výchozí pracovní plocha aplikace.",
        page_factory=DashboardPage,
        enabled=True,
    )
