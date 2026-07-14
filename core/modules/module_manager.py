from moduly.dashboard.module import get_module_definition as dashboard_module
from moduly.ukoly.module import get_module_definition as ukoly_module
from moduly.kniha_urazu.module import get_module_definition as kniha_urazu_module
from moduly.kontroly.module import get_module_definition as kontroly_module
from moduly.audity.module import get_module_definition as audity_module
from moduly.proverky.module import get_module_definition as proverky_module
from moduly.rizeni_rizik.module import get_module_definition as rizeni_rizik_module
from moduly.vysetrovani_mu.module import get_module_definition as vysetrovani_mu_module
from moduly.pravni_pozadavky.module import get_module_definition as pravni_pozadavky_module
from moduly.sprava_dat.module import get_module_definition as sprava_dat_module
from moduly.nastaveni.module import get_module_definition as nastaveni_module


class ModuleManager:
    def __init__(self):
        self.modules = [
            dashboard_module(),
            ukoly_module(),
            kniha_urazu_module(),
            kontroly_module(),
            audity_module(),
            proverky_module(),
            rizeni_rizik_module(),
            pravni_pozadavky_module(),
            vysetrovani_mu_module(),
            sprava_dat_module(),
            nastaveni_module(),
        ]

    def get_modules(self):
        return self.modules
