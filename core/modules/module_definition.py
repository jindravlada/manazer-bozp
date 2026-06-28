from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class ModuleDefinition:
    """
    Definice modulu aplikace.

    Modul sám říká:
    - svůj klíč,
    - zobrazovaný název,
    - popis,
    - zda je aktivní,
    - jak vytvořit svoji stránku.
    """

    key: str
    name: str
    description: str
    page_factory: Callable[[], QWidget]
    enabled: bool = True
