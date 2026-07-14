# Provozy a pracoviště (fáze R00)

Hierarchický číselník v modulu **Nastavení** nahrazuje původní plochý seznam „Pracoviště“.

## Struktura

| Úroveň | `item_type` | Nadřazená položka |
|--------|-------------|-------------------|
| Provoz | `operation` | — |
| Pracoviště | `workplace` | Provoz |
| Část pracoviště | `workplace_part` | Pracoviště |

Tabulka: `workplaces` (model `Workplace`).

Nová pole:

- `parent_id` – nullable FK na `workplaces.id`
- `item_type` – typ položky v hierarchii

Stávající pole zůstávají beze změny včetně `active` (soft delete) a `note`.

## Migrace

Při startu aplikace `initialize_database()` volá `_ensure_workplace_hierarchy_columns()`:

- doplní sloupce `parent_id`, `item_type`,
- všechny existující záznamy nastaví na `item_type = operation`, `parent_id = NULL`,
- **ID, názvy, aktivní stav a vazby v ostatních modulech zůstávají**.

## UI

Záložka **Provozy a pracoviště** (`NastaveniPage`):

- strom se sloupci Název / Typ / Aktivní,
- akce: Nový provoz, Nové pracoviště, Nová část pracoviště, Upravit, Aktivovat/Deaktivovat,
- dialog `WorkplaceDialog` – název, typ, nadřazená položka, aktivní, poznámka; auditní pole jen u provozu.

## Služby

- `settings_service` – CRUD a validace hierarchie při ukládání,
- `workplace_hierarchy_service` – řazení stromu, validace, detekce cyklu.

## Ostatní moduly

V této fázi se nemění. Výběry pracoviště v auditech, prověrkách a dalších modulech dál pracují se stávajícími položkami (provozy).

## Verze

Fáze R00 – interní verze aplikace 3.1.1.
