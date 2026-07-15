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

*(Odstraněno ve fázi R14 – evidence Souvislostí mezi položkami analýzy.)*

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

## Fáze R11.8

Zkvalitnění zadání pro AI oponenturu:

- exportní dialog: role oponenta, cíle oponentury, volitelná zaměření, charakteristika pracoviště
- `pokyn_pro_AI.txt` sestaven dynamicky (role, kontext, právní rámec, pravidla, otázky)
- `zadani.json` rozšířen o metadata oponentury (bez změny hierarchy dat)
- stav identifikace: první / revize, stav posouzení rizik
- import, schéma odpovědi a workflow beze změny

## Fáze R11.9

Odstranění jména odpovědné osoby z AI exportu:

- z exportního dialogu odstraněna volba „Zahrnout jméno odpovědné osoby“
- export (`zadani.json`, `data.txt`, `pokyn_pro_AI.txt`, `prehled.txt`) neobsahuje osobní údaje
- atribut `include_responsible_person` odstraněn z exportních options

## Fáze R11.10

Import odpovědi AI ve formátu JSON:

- nejdříve pokus o parse JSON dle `schema_odpovedi.json` (verze 1.1), pak fallback na textový formát
- validace identifikace, schématu a povinných polí; neplatné návrhy se přeskakují se souhrnem
- dialog načtení přijímá `.json` i `.txt`; souhrn importu uvádí použitý parser
- workflow přijetí / zamítnutí a apply podle exportních ID beze změny

## Fáze R11.11

Import odpovědi AI ze ZIP:

- dialog načtení přijímá `.json`, `.txt` i `.zip`
- ZIP se bezpečně otevře v paměti; ignorují se vnořené archivy a nepodporované typy
- preferované názvy: `odpoved_AI.json`, `odpoved.json`, `response.json`; při více souborech výběr uživatele
- parsování po načtení stejné jako u R11.10 (JSON 1.1 → text)

## Fáze R16

Číselník ohrožených skupin osob:

- společný DB číselník `exposed_groups` v Nastavení a Správě dat
- posouzení rizika používá `exposed_group_id`; textové pole zůstává jen pro migraci
- duplicita posouzení podle stejné události a stejné skupiny (ID)
- AI import vyžaduje rozhodnutí uživatele při párování na číselník

## Fáze R17a

Základ firemní knihovny vzorů:

- modely `HazardLibraryTemplate` a vazba na provozy
- stránka Firemní knihovna v modulu Řízení rizik (záložka vedle Identifikace)
- editor vzoru se záložkou Základní údaje; ostatní záložky zatím disabled
- bez ukládání obsahu identifikace a bez převzetí vzoru do identifikace

## Fáze R17b

Obsah firemního vzoru:

- modely položky, události, posouzení, existujícího a potřebného opatření ve vzoru
- záložka **Obsah vzoru** (kategorie | položky | události; dialog Posouzení a opatření)
- ruční zadávání obsahu; soft delete přes aktivní/neaktivní
- `exposed_group_id` z číselníku ohrožených skupin; závažnost jako u běžného posouzení
- automatické zvýšení `version_number` při změně obsahu (ne při úpravě základních údajů)
- neaktivní vzor: obsah pouze pro čtení
- záložky Použití a Historie zatím disabled; bez převzetí z identifikace ani použití vzoru

## Fáze R17c

Uložení položky analýzy do firemní knihovny:

- akce **Uložit do knihovny…** u vybrané aktivní položky analýzy (kromě archivované identifikace)
- dialog s názvem, popisem, rozsahem použití a volbou zahrnutí neaktivních záznamů
- kopírování celé větve (položka → události → posouzení → opatření) v jedné transakci
- audit původu: `source_identification_id`, `source_inventory_item_id`
- nový vzor má `version_number = 1`; bez přidání do existujícího vzoru

## Fáze R17d

Přechod na Master katalog zdrojů rizik:

- UI: **Katalog zdrojů rizik**, **Zdroj rizika**, **Odborný obsah**, **Použití zdroje**, **Historie změn**
- odstraněna mezivrstva `HazardLibraryTemplateItem`; `HazardLibraryTemplate` = přímo jeden Master zdroj s polem `category`
- hierarchie: Zdroj → Událost → Posouzení → Opatření (`template_id` u událostí)
- migrace bez ztráty dat: jedna položka → jeden zdroj, více položek → rozdělení na samostatné zdroje
- import z analýzy ukládá přímo nový Master zdroj; akce **Uložit do katalogu zdrojů rizik…**
- bez použití Master zdrojů v identifikaci, synchronizace a porovnání verzí

## Fáze R18a

Převzetí zdroje z katalogu do analýzy pracoviště:

- tlačítka **Přidat nový** a **Převzít z Katalogu** v záložce Analýza pracoviště
- dialog katalogu se sekcemi **Doporučené zdroje** a **Ostatní zdroje** (filtr podle kategorie a provozu identifikace)
- plná kopie větve Zdroj → Události → Posouzení → Opatření v jedné transakci
- bez vazby na Master, synchronizace a lokálních odchylek

## Fáze R18b

Evidence původu instance z katalogu:

- `HazardInventoryItem.source_template_id` a `source_template_version` se vyplní při **Převzít z Katalogu**
- verze je snímek v okamžiku převzetí (bez automatické aktualizace a porovnávání)
- ručně založené zdroje nemají původ; v dialogu položky se původ zobrazí informativně

## Fáze R18c

Lokální úpravy instancí převzatých z katalogu:

- pole `modified` u událostí, posouzení a opatření (stávající i potřebná)
- po převzetí z katalogu je `modified = False`; při uživatelské změně nebo novém záznamu na instanci s původem z katalogu se nastaví `modified = True`
- ručně založené zdroje nemění příznak `modified`
- Master katalog zůstává beze změny

## Fáze R12

Odstranění entity Nebezpečí (`IdentifiedHazard`):

- pracovní postup: Analýza pracoviště → Nežádoucí události → Posouzení → Opatření
- `HazardEvent` navázán přímo na `HazardInventoryItem` (`inventory_item_id`)
- migrace převede stávající vazby Událost→Nebezpečí→Zdroj na Událost→Zdroj a odstraní tabulku `identified_hazards`
- odstraněna záložka Nebezpečí a tlačítka identifikace/editace nebezpečí
- u položek analýzy se zobrazuje počet nežádoucích událostí
- AI export/import bez úrovně `HAZARD-###` (strom ITEM → EVENT → ASSESSMENT)

## Fáze R13

Fotodokumentace identifikace:

- záložka **Fotodokumentace** hned po Základních údajích
- model `HazardIdentificationPhoto` (metadata + relativní cesta, bez BLOB)
- soubory v `prilohy/rizeni_rizik/<číslo identifikace>/fotografie/`
- formáty JPG/JPEG/PNG/WEBP, automatická optimalizace ≤ 1 MB (EXIF orientace, bez metadat)
- náhled, otevření, aktivace/deaktivace; bez mazání a bez exportu do AI

## Fáze R14

Odstranění Souvislostí z analýzy pracoviště:

- tabulka `hazard_inventory_relations` odstraněna migrací (pouze DROP, bez převodů)
- záložka Analýza pracoviště: jen kategorie, seznam položek a akce (včetně Přidat nežádoucí událost)
- AI export bez polí a textů o souvislostech (`zadani.json` / `data.txt`)
- návrhy AI v oblasti Souvislostí se nezařazují

## Fáze R15

Sloučení Analýzy pracoviště a Nežádoucích událostí:

- záložka **Nežádoucí události** odstraněna z dialogu identifikace
- datový model `HazardEvent` beze změny
- v Analýze pracoviště: kategorie | položky (nahoře) | události vybrané položky (dole)
- automatické filtrování událostí podle výběru položky, předvyplnění zdroje při založení
- tabulka událostí bez sloupce Zdroj analýzy; počty událostí u položek
- Posouzení rizik beze změny

