from moduly.dashboard.module import get_module_definition as dashboard_module
from moduly.ukoly.module import get_module_definition as ukoly_module
from moduly.kniha_urazu.module import get_module_definition as kniha_urazu_module
from moduly.kontroly.module import get_module_definition as kontroly_module
from moduly.nastaveni.module import get_module_definition as nastaveni_module


class ModuleManager:
    def __init__(self):
        self.modules = [
            dashboard_module(),
            ukoly_module(),
            kniha_urazu_module(),
            kontroly_module(),
            nastaveni_module(),
        ]

    def get_modules(self):
        return self.modules
