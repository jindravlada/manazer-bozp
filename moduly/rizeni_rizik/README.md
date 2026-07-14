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
| `identification_number` | string | Automaticky přidělené číslo (RRRR-0001) |
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

- Identifikace
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

## Fáze R03

Analýza inventury v záložce Inventura:

- model `HazardInventoryRelation` v tabulce `hazard_inventory_relations`
- sekce Analýza položky se souvislostmi podle typu a kategorie
- samostatné ukládání vazeb, počty aktivních souvislostí u položek
- režim pouze pro čtení u dokončené nebo archivované identifikace

## Fáze R04

Evidence nebezpečí v záložce Nebezpečí:

- model `IdentifiedHazard` v tabulce `identified_hazards`
- ruční evidence nebezpečí navázaných na položky inventury
- akce Identifikovat nebezpečí v inventuře, počty aktivních nebezpečí u položek
- režim pouze pro čtení u dokončené nebo archivované identifikace

## Fáze R04a

Identifikace bez názvu:

- pole `title` nahrazeno automatickým `identification_number` ve formátu RRRR-0001
- migrace stávajících záznamů a odstranění sloupce `title`
- editor zobrazuje read-only číslo identifikace

## Fáze R05

Nežádoucí události v záložce Nežádoucí události:

- model `HazardEvent` v tabulce `hazard_events`
- události navázané na identifikovaná nebezpečí
- akce Přidat nežádoucí událost v záložce Nebezpečí, počty aktivních událostí u nebezpečí
- režim pouze pro čtení u dokončené nebo archivované identifikace
