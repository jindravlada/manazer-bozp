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

Rozšíření posouzení rizika o závažnost a více ohrožených skupin:

- pole `severity` v modelu `HazardRiskAssessment` (jediné hodnocení následku)
- vazba M:N na ohrožené skupiny (`hazard_risk_assessment_exposed_groups`)
- pět úrovní závažnosti se slovní popisem v dialogu
- sloupce Ohrožené skupiny a Závažnost v záložce Posouzení rizik
- validace povinných polí; aktivní posouzení se nesmí překrývat v ohrožených skupinách u stejné události

## Fáze R08

Existující opatření u posouzení rizika (UI: Zásady bezpečné práce):

- model `HazardExistingMeasure` v tabulce `hazard_existing_measures`
- sekce Zásady bezpečné práce po výběru posouzení v záložce Posouzení rizik
- samostatné ukládání opatření, počty aktivních opatření u posouzení
- režim pouze pro čtení u dokončené nebo archivované identifikace

## Fáze R09

Potřebná další opatření u posouzení rizika (UI: Navazující opatření):

- model `HazardRequiredMeasure` v tabulce `hazard_required_measures`
- sekce Navazující opatření pod zásadami bezpečné práce v záložce Posouzení rizik
- samostatné ukládání opatření, počty aktivních navazujících opatření u posouzení
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

## Fáze R16a

Zjednodušení číselníku ohrožených skupin:

- výchozí seed obsahuje pouze **Zaměstnanci daného pracoviště** a **Dodavatelé**
- vyhledávací výběr `ExposedGroupSelector` s filtrováním při psaní a vytvořením nové skupiny
- bez jednorázového použití; každá nová skupina se ukládá do číselníku
- neaktivní shoda při vytváření nabídne aktivaci, aktivní duplicita je zakázána
- správa číselníku zobrazuje názvy a podporuje Přidat / Upravit / Aktivovat / Deaktivovat

## Fáze R16a.1

Vyčištění číselníku při startu aplikace:

- seed při každém spuštění obnoví pouze dvě výchozí položky
- testovací a uživatelsky přidané položky z předchozích běhů se při startu odstraní

## Fáze R16a.2

Bezpečný seed ohrožených skupin:

- seed nemaže existující obsah tabulky
- výchozí dvě položky se vloží pouze do prázdné tabulky (nová databáze)
- uživatelsky přidané skupiny zůstávají zachované při dalších startech

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
- zvýšení `version_number` jednou po editační relaci nebo hromadné operaci (ne při každém dílčím zápisu)
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

## Fáze R18d

Porovnání lokální instance s Master katalogem:

- tlačítko **Porovnat s Masterem…** u zdroje převzatého z katalogu
- read-only přehled odchylek: `+` nová položka, `−` odebraná položka, `~` změněný text
- porovnání proti aktuálnímu Master obsahu; bez aktualizace instance

## Fáze R18e

Aktualizace lokální instance z novější verze Master:

- při výběru zdroje s novější verzí Master program nabídne **Aktualizovat**, **Zobrazit rozdíly** nebo **Ponechat**
- zobrazení verze instance → Master (např. v7 ↓ v8)
- aktualizace pouze po explicitní volbě uživatele; automatické přepsání nikdy
- po aktualizaci se obnoví obsah z Master a `source_template_version` se srovná s aktuální verzí

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

## Fáze R18f

Oponentura AI v Katalogu zdrojů rizik:

- záložka **Oponentní posouzení AI** v editoru zdroje rizika (po prvním uložení)
- provider `hazard_catalog_source` s exportem MASTER hierarchie (`SOURCE` → `EVENT` → `ASSESSMENT` → opatření)
- exportní dialog bez cíle „Hledat chybějící zdroje analýzy“, pole **Obecný kontext zdroje rizika**
- import JSON/TXT/ZIP pouze do evidence konzultace (návrhy se nezapisují do MASTER obsahu)
- v identifikaci pracoviště je nový export/import AI vypnutý; historická konzultace zůstává zobrazena

## Fáze R18f.1 (evidence importu)

Oprava evidence importovaných návrhů v katalogu:

- stavy návrhů: **Čeká na odborné posouzení**, **Zamítnuto**, **Nezařazeno** (bez falešného „Převzato“)
- souhrn importu a historie konzultací s počty podle stavů
- návrhy se ukládají do databáze včetně `proposal_id` a vazby na konzultaci
- opakované načtení odpovědi: nová konzultace / nahrazení / zrušení
- tabulka návrhů vybrané konzultace se obnoví ihned po importu

## Fáze R18g.0

Oprava verzování Master zdroje rizika:

- dílčí služby obsahu nevolají bump verze
- editor eviduje změnu odborného obsahu a zvýší verzi nejvýše o 1 při zavření
- nový zdroj zůstává na verzi 1 i po prvotním naplnění obsahu
- hromadné operace mají jeden explicitní bump po dokončení transakce

## Fáze R18g.1

Revize odborného obsahu místo verzí:

- v UI katalogu se pojem **Verze** nahrazuje pojmem **Revize** (datové pole `version_number` zůstává)
- záložka **Historie změn** eviduje revize s číslem, datem a automatickým důvodem změny
- důvody: ruční úprava, import z identifikace, návrhy AI, aktualizace z Master
- model `hazard_library_template_revisions` je připraven pro budoucí autora, seznam změn, komentář a obnovu

## Fáze R18g.2

Inteligentní zpracování duplicit při zapracování AI návrhů:

- jednoznačné shody v číselnících a textech se sloučí automaticky bez dialogu
- dialog se zobrazí pouze u podobných shod a nejasných duplicit odborného obsahu
- po dokončení zapracování se zobrazí souhrnné hlášení (nově zapracováno, použito existujících, přeskočeno, revize)

## Fáze R19

Právní vazby katalogu a dokončení AI workflow:

- nová úroveň **Právní vazby** u zdroje rizika (vazba na RPP, poznámka, aktivní, pořadí)
- správa v editoru odborného obsahu (Přidat / Upravit / Aktivovat / Deaktivovat)
- AI návrh právní vazby: automatická shoda, výběr při více kandidátech, jinak návrh zůstane ve frontě
- opatření navázané na SOURCE: dialog výběru posouzení místo chyby
- srozumitelné chybové hlášky a rozšířené souhrnné hlášení po zapracování

## Fáze R19a

Zobrazení zdrojů rizik ve Vazbách a použití:

- u právního požadavku automatická sekce Zdroje rizik s aktivními katalogovými vazbami
- u procesu odvozené zobrazení zdrojů navázaných na aktivní podřízené požadavky
- dvojklik otevře zdroj v katalogu zdrojů rizik

## Fáze R19.1

Průvodce ručním dokončením zapracování:

- po automatickém zapracování s návrhy vyžadujícími ruční zásah nabídne průvodce (výchozí) nebo odložení
- průvodce postupně vybere problémový návrh, otevře odpovídající dialog a po vyřešení pokračuje na další
- finální souhrn se zobrazí až po dokončení všech ručních kroků

## Fáze R19.2

Dokončení ručního přiřazení opatření k posouzení:

- po výběru posouzení se návrh okamžitě zapracuje (nové opatření, stav Zapracováno, obnovení UI)
- dialog výběru posouzení zobrazuje událost a ohroženou skupinu zvlášť
- jediné vhodné posouzení se přiřadí automaticky bez dialogu
- chybí-li vhodné posouzení, lze založit nové nebo návrh ponechat ve frontě

## Fáze R19.2.1

Dokončení workflow po ručním rozhodnutí:

- po výběru posouzení nebo právního požadavku se návrh okamžitě zapracuje
- stav se změní na Zapracováno, objekt vznikne v MASTER a UI se obnoví
- průvodce R19.1 teprve potom pokračuje na další problémový návrh

## Fáze R20a

AI oponentura katalogu jako ucelené návrhové balíky (schema 2.0):

- export katalogu používá `schema_odpovedi.json` verze 2.0 s `proposal_packages`
- každý balík obsahuje událost (nebo vazbu na EVENT-…), posouzení, opatření a právní vazby
- validace odmítne neúplné balíky; neplatný balík se neimportuje částečně
- atomizovaný import schema 1.1 nelze načíst do nových katalogových konzultací
- schema 1.1 zůstává pro čtení historických odpovědí identifikace rizik
- UI zobrazuje přehled načtených balíků; zápis do MASTER zatím není implementován

## Fáze R20b

UI a zapracování návrhových balíků:

- po výběru balíku se zobrazí Detail balíku (událost, posouzení, opatření, právní vazby, zdůvodnění)
- akce **Upravit balík…**, **Zapracovat balík**, **Zamítnout balík**
- editor upravuje celý balík najednou (nikoliv izolované objekty)
- zapracování probíhá v jedné DB transakci (událost → posouzení → opatření → právní vazby → revize +1 → historie) s rollbackem při chybě

## Fáze R20b.1

Normalizace právních odkazů AI vůči RPP:

- zkratky NV / vyhl. / zák. se ekspandují na plný název předpisu
- primární párování podle čísla a roku předpisu (např. `NV 378/2001` ↔ `Nařízení vlády č. 378/2001 Sb.`)
- jedna shoda se použije automaticky; více shod zůstane k ručnímu výběru

## Fáze R18g

Zapracování návrhů AI do MASTER obsahu katalogu:

- stav **Čeká na odborné posouzení** a akce Zapracovat / Zamítnout / Upravit
- hromadné zapracování v jedné transakci se zvýšením Revize o 1
- historie změn s důvodem „Převzaty návrhy AI“
- detekce duplicit s volbami Přeskočit / Sloučit / Upravit / Zrušit

## RISK-REVIEW-1

Přezkoumání opatření rizik:

- záložka Přezkoumání opatření v modulu Řízení rizik
- entity `RiskMeasureReview` a `RiskMeasureReviewItem` (vazba na `hazard_required_measures.id`)
- editor hlavičky (checklist se generuje v další fázi)
- UI přejmenování: Zásady bezpečné práce / Navazující opatření

## RISK-REVIEW-2

Generování checklistu přezkoumání:

- Navazující opatření mají `title` (Název) a volitelný popis (`note`)
- při vytvoření přezkoumání se z rozsahu Provoz/Pracoviště/Část vygenerují položky checklistu
- položky odkazují na `follow_up_measure_id`; při znovuotevření se negenerují znovu
- editor zobrazuje tabulku Riziko / Navazující opatření / Výsledek / Poznámka

## RISK-REVIEW-2a

Zjednodušení checklistu pro terén:

- sloupce Navazující opatření / Vyhovuje / Poznámka č. / Foto
- sekce Poznámky pod checklistem (zatím jen rozvržení)
- kompaktní rozložení vhodné pro A4

## RISK-REVIEW-3

Evidence zjištění:

- entita `RiskMeasureFinding` vázaná na číslo poznámky v checklistu
- automatické vytvoření zjištění při zadání nového čísla
- záložka Zjištění v editoru přezkoumání
- upozornění při neúplném názvu (uložení se nezakazuje)
