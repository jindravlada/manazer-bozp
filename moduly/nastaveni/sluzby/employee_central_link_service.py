"""Výslovné propojení zaměstnance z Testů s centrální evidencí.

Služba nikdy nespojuje záznamy podle jména, příjmení ani podobnosti údajů.
Osobní číslo vrací jen jako nápovědu. Propojení vznikne až voláním
``link_existing`` nebo ``create_and_link``. ``unlink`` maže jen řádek mapy
požadované dvojice.
"""

from moduly.nastaveni.modely.test_employee_central_link import TestEmployeeCentralLink
from moduly.nastaveni.modely.thp_worker import ThpWorker
from moduly.nastaveni.repository.employee_central_link_repository import (
    EmployeeCentralLinkRepository,
    EmployeeLinkError,
    EmployeeUnlinkResult,
)

__all__ = [
    "EmployeeLinkError",
    "EmployeeUnlinkResult",
    "EmployeeCentralLinkService",
    "employee_central_link_service",
]


class EmployeeCentralLinkService:
    def __init__(self) -> None:
        self.repository = EmployeeCentralLinkRepository()

    def get_by_test_employee(
        self,
        test_employee_id: int | None,
    ) -> TestEmployeeCentralLink | None:
        if not test_employee_id:
            return None
        return self.repository.get_by_test_employee(int(test_employee_id))

    def get_by_worker(
        self,
        thp_worker_id: int | None,
    ) -> TestEmployeeCentralLink | None:
        if not thp_worker_id:
            return None
        return self.repository.get_by_worker(int(thp_worker_id))

    def personal_number_hints(self, test_employee_id: int) -> list[ThpWorker]:
        """Stejné osobní číslo v centrální evidenci. Nic nepropojuje."""
        return self.repository.personal_number_hints(int(test_employee_id))

    def link_existing(
        self,
        *,
        test_employee_id: int,
        thp_worker_id: int,
    ) -> TestEmployeeCentralLink:
        """Propojí dva existující záznamy a jejich údaje nechá beze změny."""
        return self.repository.link_existing(
            test_employee_id=int(test_employee_id),
            thp_worker_id=int(thp_worker_id),
        )

    def create_and_link(self, test_employee_id: int) -> TestEmployeeCentralLink:
        """Založí centrálního zaměstnance z údajů Testů a hned ho propojí.

        Vytvoření i propojení je jedna transakce. Vedoucí / THP a provádění
        kontrol jsou u nového záznamu ne. Původní zaměstnanec v Testech zůstává.
        """
        return self.repository.create_and_link(int(test_employee_id))

    def unlink(
        self,
        *,
        test_employee_id: int,
        thp_worker_id: int,
    ) -> EmployeeUnlinkResult:
        """Zruší propojení jen tehdy, když uložená vazba je přesně tato dvojice.

        Odstraní pouze řádek mapy. Zaměstnance, role a zkoušky nemění.
        Chybějící dvojice nic nemaže a vrátí srozumitelný výsledek.
        """
        return self.repository.unlink(
            test_employee_id=int(test_employee_id),
            thp_worker_id=int(thp_worker_id),
        )


employee_central_link_service = EmployeeCentralLinkService()
