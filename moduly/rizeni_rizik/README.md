# Modul Řízení rizik

Modul pro evidenci identifikací nebezpečí a následné řízení rizik v organizaci.

## Fáze R01a

Založení modulu:

- model `HazardIdentification` (`hazard_identifications`)
- stránka se seznamem identifikací
- registrace v hlavním menu

Editor identifikace a dialog založení záznamu nejsou součástí této fáze.

## Struktura

```
moduly/rizeni_rizik/
├── module.py
├── constants.py
├── modely/
│   └── hazard_identification.py
├── repository/
│   └── hazard_identification_repository.py
├── sluzby/
│   └── hazard_identification_service.py
└── ui/
    ├── rizeni_rizik_page.py
    └── hazard_identification_table.py
```

## Model HazardIdentification

| Pole | Typ | Poznámka |
|------|-----|----------|
| `title` | string | Název identifikace |
| `operation_id` | int | Provoz |
| `workplace_id` | int | Pracoviště |
| `workplace_part_id` | int, nullable | Část pracoviště |
| `responsible_person_id` | int, nullable | Osoba z číselníku `persons` |
| `started_at` | date, nullable | Datum zahájení |
| `status` | string | `draft`, `in_progress`, `completed`, `archived` |
| `note` | text | Poznámka |
| `active` | bool | Soft delete |
| `created_at`, `updated_at` | datetime | Auditní pole |

Denormalizovaná jména (`operation_name`, `workplace_name`, …) se ukládají pro zobrazení v seznamu.

## Seznam identifikací

Stránka `RizeniRizikPage` zobrazuje tabulku se sloupci:

- Název
- Provoz
- Pracoviště
- Datum zahájení
- Odpovědná osoba
- Stav

Řazení: datum zahájení sestupně.

Tlačítka Nová identifikace / Upravit / Aktivovat / Deaktivovat jsou připravena, ale zatím nejsou funkční.

## Fáze R01b

Editor identifikace (`HazardIdentificationDialog`):

- záložky dle metodiky modulu, funkční pouze **Základní údaje**
- dynamické nabídky Pracoviště / Část pracoviště podle hierarchie provozů
- založení, editace, uložení, načtení, aktivace a deaktivace bez fyzického mazání

## Fáze R02

Záložka **Inventura** (`HazardInventoryWidget`):

- model `HazardInventoryItem` v tabulce `hazard_inventory_items`
- přehled podle 9 kategorií s počtem aktivních položek
- samostatné ukládání položek inventury bez zavírání editoru identifikace
- u dokončené nebo archivované identifikace pouze režim pro čtení
