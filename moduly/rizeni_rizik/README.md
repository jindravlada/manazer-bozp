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

Záložka **Analýza pracoviště** (`HazardInventoryWidget`):

- model `HazardInventoryItem` v tabulce `hazard_inventory_items`
- přehled podle 9 kategorií s počtem aktivních položek analýzy
- samostatné ukládání položek analýzy pracoviště bez zavírání editoru identifikace
- u dokončené nebo archivované identifikace pouze režim pro čtení

## Fáze R03

Souvislosti v záložce Analýza pracoviště:

- model `HazardInventoryRelation` v tabulce `hazard_inventory_relations`
- sekce Analýza položky se souvislostmi podle typu a kategorie
- samostatné ukládání vazeb, počty aktivních souvislostí u položek
- režim pouze pro čtení u dokončené nebo archivované identifikace

## Fáze R04

Evidence nebezpečí v záložce Nebezpečí:

- model `IdentifiedHazard` v tabulce `identified_hazards`
- ruční evidence nebezpečí navázaných na položky analýzy pracoviště
- akce Identifikovat nebezpečí v analýze pracoviště, počty aktivních nebezpečí u položek
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

## Fáze R05a

Přejmenování uživatelské terminologie:

- záložka **Inventura** přejmenována na **Analýza pracoviště**
- uživatelské texty používají termín položka analýzy / analýza pracoviště
- interní názvy modelů, tabulek a služeb zůstávají beze změny

## Fáze R06

Posouzení rizik v záložce Posouzení rizik:

- model `HazardRiskAssessment` v tabulce `hazard_risk_assessments`
- evidence ohrožených skupin osob navázaných na nežádoucí události
- akce Posoudit riziko v záložce Nežádoucí události, počty aktivních posouzení u událostí
- režim pouze pro čtení u dokončené nebo archivované identifikace

## Fáze R07

Rozšíření posouzení rizika o následek a závažnost:

- pole `consequence` a `severity` v modelu `HazardRiskAssessment`
- pět úrovní závažnosti se slovní popisem v dialogu
- sloupce Možný následek a Závažnost v záložce Posouzení rizik
- validace povinných polí bez změny pravidel duplicity ohrožené skupiny

## Fáze R08

Existující opatření u posouzení rizika:

- model `HazardExistingMeasure` v tabulce `hazard_existing_measures`
- sekce Existující opatření po výběru posouzení v záložce Posouzení rizik
- samostatné ukládání opatření, počty aktivních opatření u posouzení
- režim pouze pro čtení u dokončené nebo archivované identifikace

## Fáze R09

Potřebná další opatření u posouzení rizika:

- model `HazardRequiredMeasure` v tabulce `hazard_required_measures`
- sekce Potřebná další opatření pod existujícími opatřeními v záložce Posouzení rizik
- samostatné ukládání opatření, počty aktivních potřebných opatření u posouzení
- režim pouze pro čtení u dokončené nebo archivované identifikace

## Fáze R10

Dokončení posouzení rizika:

- pole `assessment_status`, `conclusion` a `completed_at` u modelu `HazardRiskAssessment`
- stavy Rozpracováno / Dokončeno, validace úplnosti před dokončením
- sloupce Stav posouzení a Dokončeno dne v záložce Posouzení rizik
- souhrn počtu rozpracovaných a dokončených aktivních posouzení
- režim pouze pro čtení stavu a závěru u dokončené nebo archivované identifikace

## Fáze R11

Export podkladů pro konzultaci s AI (původní varianta):

- záložka Konzultace s AI, model `HazardAiExport`
- ZIP s `zadani.json` a schématem odpovědi

## Fáze R11.2

Přestavba na obecný modul **Oponentní posouzení AI** (`core/ai_oponentni`):

- AI jako nezávislý odborný konzultant BOZP (ne jako doplňování databáze)
- načtení odpovědi AI a ruční převzetí / zamítnutí návrhů
- evidence konzultací (datum, model AI, prompt, odpověď, počty převzatých/zamítnutých)
- doménový adaptér pro identifikaci nebezpečí; stejný mechanismus půjde použít i v jiných modulech

## Fáze R11.3

Hierarchický export AI:

- strom: Analýza pracoviště → Nebezpečí → Události → Posouzení → Opatření
- stabilní exportní ID (`ITEM-001`, `HAZARD-001`, `EVENT-001`, `ASSESSMENT-001`)
- ZIP: `pokyn_pro_AI.txt`, `data.txt`, `prehled.txt`, `zadani.json`, `schema_odpovedi.json`

## Fáze R11.4

Bezpečný hierarchický import AI:

- import výhradně podle exportních ID z mapy uložené při exportu
- chybějící / neplatný rodič → model `AiUnassignedProposal` (Nezařazený návrh)
- zákaz fallbacku „připojit k prvnímu“
- UI pro nezařazené návrhy zatím není

## Fáze R11.5

Příprava dávkového exportu:

- metadata v `zadani.json`: `export_scope`, `batch_number`, `batch_count`
- zatím vždy `full` / `1` / `1` (dávkování se neimplementuje)

## Fáze R11.6

Příprava změnového exportu:

- objekt `change_tracking` v `zadani.json`: `mode`, `base_export`, `changed_objects`
- výchozí: `full` / `null` / `[]` (logika změnového exportu se neimplementuje)

## Fáze R11.7

Dávkový export AI podle zdrojů analýzy:

- dávka = celé hierarchické větve vybraných zdrojů (větev se nerozděluje)
- limity: max. 10 zdrojů / 200 objektů na dávku (pojmenované konstanty)
- nadlimitní jediná větev → samostatná dávka + `recommended_limit_exceeded`
- dialog rozsahu: celá identifikace (výchozí) / vybrané zdroje
- více dávek → hlavní ZIP (`davka_00N.zip` + `prehled_davek.txt`)
- jedna společná konzultace a mapa exportních ID pro celý export

