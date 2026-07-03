# Globální vyhledávání — architektura

> **Commit 1 — návrhový dokument**
>
> Tento dokument popisuje architekturu **globálního vyhledávání** v aplikaci Manažer BOZP 3.0.
> Neobsahuje implementaci databáze, UI ani konkrétní kód modulů.
> Slouží jako schvalovací podklad pro následnou implementaci po malých commitech.

---

## Filozofie

Globální vyhledávání **není funkce jednoho modulu**. Je to **společná služba aplikace** (`core`), ke které se připojují jednotlivé moduly jako poskytovatelé výsledků.

Uživatel zadá text a dostane **výsledky napříč moduly**. Každý výsledek musí být **otevřitelný** — dvojklik nebo Enter otevře příslušný dialog nebo záznam v cílovém modulu.

Vyhledávání je **navigační nástroj**, ne report. Cílem je rychle najít entitu a přejít k ní.

### Vztah k současnému stavu

V aplikaci již existuje prototyp `core/search/global_search_service.py` s monolitickou implementací (úrazy, úkoly, THP, pracoviště, zaměstnavatel) a jednoduchým polem v hlavním toolbaru. Tento návrh popisuje **cílovou architekturu V1**, která:

- rozloží logiku do providerů podle modulů,
- sjednotí datový model výsledku,
- propojí otevírání se stávajícím `SourceNavigator` kde to dává smysl,
- připraví půdu pro dialog vyhledávání a klávesové zkratky v dalších commitech.

Migrace proběhne postupně — stará služba se nahradí refaktorovanou verzí, ne paralelním duplicitním řešením.

---

## Minimální rozsah V1

Vyhledávání musí být **architektonicky připravené** pro tyto domény:

| Doména | Modul / kontext | Priorita V1 |
|--------|-----------------|-------------|
| Úkoly | `ukoly` | ano — první provider |
| Audity | `audity` | ano |
| Program auditů | `audity` (Manažer auditů) | ano |
| Zjištění | napříč moduly (`finding`) | ano |
| Prověrky | `proverky` | ano |
| Kniha úrazů | `kniha_urazu` | ano |
| Pracoviště | `nastaveni` | ano |
| THP / osoby | `nastaveni` | ano |

### Plánované rozšíření (po V1)

| Doména | Poznámka |
|--------|----------|
| Přehled právních požadavků | samostatný modul / registr |
| Registr rizik | budoucí modul |
| Školení | budoucí modul |
| OOPP | budoucí modul |
| Řídicí dokumentace | budoucí modul |

Nový modul = nový `SearchProvider` + registrace v agregátoru. **Datový model `SearchResult` se nemění.**

---

## Datový model — `SearchResult`

Obecný výsledek hledání reprezentuje **jeden nalezený záznam** bez ohledu na modul.

```python
@dataclass(frozen=True)
class SearchResult:
    source_type: str          # kanonický typ entity, např. "task", "audit", "finding"
    source_id: int            # primární klíč záznamu v doméně providera
    title: str                # hlavní řádek ve výsledcích
    subtitle: str             # doplňující kontext (stav, osoba, datum…)
    description: str          # volitelný třetí řádek / tooltip
    module_key: str           # klíč modulu pro navigaci (např. "ukoly", "audity")
    module_label: str         # lidský název modulu pro seskupení v UI
    priority: int             # nižší = výše ve výsledcích (0 = nejvyšší)
    metadata: dict[str, str]  # volitelná data pro řazení / zobrazení (bez business logiky v UI)
```

### Pole a význam

| Pole | Účel |
|------|------|
| `source_type` | Stabilní identifikátor typu pro `open_result()` — nesmí být závislý na UI |
| `source_id` | ID záznamu k otevření |
| `title` | Co uživatel primárně hledá (název, číslo, popis) |
| `subtitle` | Kontext: stav, termín, pracoviště, odpovědná osoba |
| `description` | Delší úryvek nebo poznámka; v dialogu volitelně třetí řádek |
| `module_key` | Pro `_show(module_key)` v hlavním okně |
| `module_label` | Pro seskupení v budoucím dialogu („Úkoly“, „Audity“…) |
| `priority` | Pořadí u stejné relevance — např. aktivní úkol před ukončeným |
| `metadata` | Např. `{"status": "Probíhá", "due_date": "2026-04-15"}` — bez typové magie v UI |

### Odvozené vlastnosti (volitelně)

- `display` — formátovaný řádek pro autocomplete / seznam (zachovat zpětnou kompatibilitu s toolbar completerem).
- `group_key` — defaultně `module_label`, pro seskupení v dialogu.

### Konstanty `source_type` (V1)

| `source_type` | Popis |
|---------------|--------|
| `task` | Úkol / opatření |
| `audit` | Audit systémů řízení |
| `audit_program` | Program auditů (Manažer auditů) |
| `finding` | Zjištění (napříč entitami) |
| `bozp_inspection` | Prověrka BOZP |
| `accident` | Záznam knihy úrazů |
| `workplace` | Pracoviště |
| `person` | THP pracovník / odpovědná osoba |
| `employer` | Zaměstnavatel (volitelně V1) |
| `action` | **Budoucí** — spuštění aplikční akce (Command Palette), viz níže |

Konstanty patří do `core/search/constants.py` (ne do modulů).

Typ `action` **není součástí V1** — dokumentován pro budoucí rozšíření na Command Palette.

---

## Architektura služeb

### Přehled vrstev

```
┌─────────────────────────────────────────────────────────┐
│  UI (až Commit 3+)                                      │
│  toolbar / dialog / Ctrl+K                              │
└──────────────────────────┬──────────────────────────────┘
                           │ search(query)
┌──────────────────────────▼──────────────────────────────┐
│  GlobalSearchService (agregátor)                        │
│  — normalizace dotazu                                   │
│  — volání providerů                                     │
│  — sloučení, řazení, limit                              │
│  — open_result(result)                                  │
└──────────────────────────┬──────────────────────────────┘
                           │ search(query) per provider
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  TaskSearchProvider  AuditSearchProvider  …
        │                  │                  │
        ▼                  ▼                  ▼
  task_service       audit_service      … (existující služby modulů)
```

Umístění souborů (cílová struktura):

```
core/search/
├── __init__.py
├── constants.py              # source_type, limity, prahové hodnoty
├── models.py                 # SearchResult, SearchQuery
├── search_provider.py        # abstraktní rozhraní SearchProvider
├── global_search_service.py  # agregátor + open_result
├── result_opener.py          # mapování source_type → opener (volitelně Commit 4)
└── providers/
    ├── __init__.py
    ├── task_search_provider.py
    ├── audit_search_provider.py
    ├── audit_program_search_provider.py
    ├── finding_search_provider.py
    ├── proverky_search_provider.py
    ├── accident_search_provider.py
    ├── workplace_search_provider.py
    └── people_search_provider.py
```

Moduly **neexportují** vyhledávání ven — provider volá jejich existující `*_service` / `repository`. Provider je tenká vrstva nad read-only dotazy.

---

## Rozhraní `SearchProvider`

Každý modul (nebo doména) implementuje společné rozhraní:

```python
class SearchProvider(Protocol):
    provider_key: str       # např. "tasks"
    module_key: str         # např. "ukoly"
    module_label: str         # např. "Úkoly"

    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        """Vrátí nalezené záznamy. Prázdný seznam = nic nenalezeno."""
        ...
```

### Pravidla pro providery

1. **Minimální délka dotazu** — agregátor kontroluje globálně (V1: 2 znaky); provider může předpokládat normalizovaný dotaz.
2. **Bez side-effectů** — pouze čtení dat.
3. **Respektovat limit** — provider vrací nejvýše `limit` kandidátů; agregátor může limit ještě znovu aplikovat po sloučení.
4. **Nezávislost na UI** — žádné importy `PySide6` v provideru.
5. **Izolace chyb** — výjimka v provideru nesmí shodit celé vyhledávání (viz níže).

### Registrace providerů

Agregátor drží seznam providerů v pevném pořadí (priorita modulů ve výsledcích):

1. Úkoly  
2. Audity  
3. Program auditů  
4. Zjištění  
5. Prověrky  
6. Kniha úrazů  
7. Pracoviště  
8. THP / osoby  

Pořadí lze později konfigurovat; V1 stačí konstanta v `global_search_service.py`.

---

## Agregátor — `GlobalSearchService`

### Veřejné API (V1)

```python
class GlobalSearchService:
    def search(self, text: str, *, limit: int = 30) -> list[SearchResult]: ...

    def open_result(self, result: SearchResult, host) -> bool: ...
```

### Algoritmus `search`

1. Normalizovat dotaz (`strip`, lowercase pro porovnání).
2. Pokud `len(query) < MIN_QUERY_LENGTH` → `[]`.
3. Pro každého providera v pořadí:
   - zavolat `provider.search(query, limit=limit)` uvnitř `try/except`,
   - při chybě zalogovat a pokračovat,
   - přidat výsledky do společného seznamu.
4. Seřadit sloučený seznam:
   - primárně podle shody v `title` (exact prefix > contains),
   - sekundárně `priority`,
   - terciárně `title` abecedně.
5. Oříznout na `limit`.
6. Vrátit seznam.

V1 **nemusí** mít sofistikované skóre relevance — stačí jednoduché pořadí + limit. Pole `priority` v `SearchResult` umožní providerům zvýhodnit aktivní záznamy.

### Strategie dotazů (V1)

- **SQLite LIKE** `%query%` nad relevantními sloupci v repository / service.
- Načtení kandidátů v paměti s `_contains()` (jako dnes) je přijatelné pro malé datasety; u větších modulů provider přesune filtr do SQL.

Provider volá existující repository metody typu `list_for_search(query)` — ty se doplní až v commitech konkrétních modulů, ne v Commit 1.

---

## Otevírání výsledků

Každý výsledek musí být **otevřitelný** jednotným vstupním bodem.

### Mechanismus

```python
def open_result(self, result: SearchResult, host) -> bool:
    """
    host = MainWindow nebo tenký SearchHost protocol
    Vrátí True, pokud se podařilo otevřít záznam.
    """
```

Mapování `source_type` → akce:

| `source_type` | Modul | Otevření |
|---------------|-------|----------|
| `task` | `ukoly` | `UkolyPage.open_task(source_id)` → `TaskDialog` |
| `audit` | `audity` | `AudityPage.open_audit(source_id)` → `AuditDialog` |
| `audit_program` | `audity` | `AudityPage.open_program_manager()` + výběr programu `source_id` |
| `finding` | dle entity zjištění | `SourceNavigator.open(entity_type, entity_id)` + později fokus zjištění |
| `bozp_inspection` | `proverky` | `ProverkyPage.open_inspection(source_id)` → `BozpInspectionDialog` |
| `accident` | `kniha_urazu` | `KnihaUrazuPage.open_accident(source_id)` → `AccidentDialog` |
| `workplace` | `nastaveni` | `NastaveniPage.open_workplace(source_id)` → `WorkplaceDialog` |
| `person` | `nastaveni` | `NastaveniPage.open_worker(source_id)` → `ThpWorkerDialog` |

### Integrace s `SourceNavigator`

Pro entity již registrované v `core/navigation/source_navigator.py` (`ENTITY_AUDITY`, `ENTITY_ACCIDENT`, …) preferovat existující routes místo duplicitní logiky.

Pro typy bez route (úkol, pracoviště, program auditů) agregátor nebo `ResultOpener` registruje **openery** analogicky k `SourceNavigator.register()`.

### Rozhraní openeru (Commit 4)

```python
class SearchResultOpener(Protocol):
    def can_open(self, result: SearchResult) -> bool: ...
    def open(self, host, result: SearchResult) -> bool: ...
```

Registrace v `global_search_service` nebo samostatném `SearchResultRouter`.

---

## UI — návrh (implementace až po Commit 3)

Zatím **pouze návrh**, bez kódu.

### Fáze 1 — stávající toolbar (dočasně)

- Pole „Globální vyhledávání…“ v hlavním okně (již existuje).
- Autocomplete se seznamem `SearchResult.display`.
- Enter / klik otevře první / vybraný výsledek.

### Fáze 2 — dialog vyhledávání (Commit 3)

- Modální / nemodální dialog `GlobalSearchDialog`.
- Vyhledávací pole nahoře, seznam výsledků pod ním.
- **Seskupení podle `module_label`** (collapsible sekce nebo mezery).
- Šipky ↑↓, Enter = otevřít, Esc = zavřít.
- Dvojklik na řádek = `open_result()`.

### Klávesová zkratka (Commit 6)

- **Ctrl+K** nebo **Ctrl+F** — otevře dialog vyhledávání a fokus do pole.
- Konflikt s lokálním hledáním v tabulkách řešit kontextem: globální zkratka jen v hlavním okně, lokální filter v modulech zůstává.

---

## Budoucí rozšíření: Command Palette

> **Mimo rozsah V1.** Tato kapitola popisuje směr vývoje po dokončení základního globálního vyhledávání dat. **Command Palette se v Commit 1–6 neimplementuje.**

### Účel

Globální vyhledávání může být v budoucnu rozšířeno tak, aby nesloužilo **jen k hledání datových objektů**, ale i ke **spouštění akcí** v aplikaci — podobně jako paleta příkazů (Command Palette) v moderních IDE (VS Code, IntelliJ, Cursor).

Uživatel zadá text a kromě nalezených záznamů uvidí i **příkazy**, které může okamžitě spustit.

### Příklady dotazů a akcí

| Dotaz uživatele | Typ výsledku | Co se stane |
|-----------------|--------------|-------------|
| nový audit | `action` | Otevře dialog nového auditu |
| nová prověrka | `action` | Otevře dialog nové prověrky |
| nový úkol | `action` | Otevře dialog nového úkolu |
| manažer auditů | `action` | Otevře Manažer auditů |
| editor metodiky | `action` | Otevře editor znalostí auditora |
| záloha databáze | `action` | Spustí zálohu databáze |
| obnova databáze | `action` | Spustí obnovu ze zálohy |
| přehled právních požadavků | `action` | Přejde do modulu / přehledu (až bude existovat) |
| registr rizik | `action` | Přejde do modulu rizik (až bude existovat) |

Akce se registrují deklarativně — stejně jako search providery — a filtrují se podle aliasů, klíčových slov a českých synonym.

### Typ výsledku `action`

Vedle běžných objektů:

| `source_type` | Kategorie |
|---------------|-----------|
| `task` | datový objekt |
| `audit` | datový objekt |
| `finding` | datový objekt |
| `bozp_inspection` | datový objekt |
| `accident` | datový objekt |
| `workplace` | datový objekt |
| `person` | datový objekt |

přibude typ:

| `source_type` | Kategorie |
|---------------|-----------|
| `action` | aplikční příkaz |

U výsledku typu `action`:

- `source_id` může být `0` nebo interní ID akce v registru příkazů,
- `metadata` obsahuje např. `{"action_key": "audit.new"}` — stabilní identifikátor pro spuštění,
- `title` = lidský název akce („Nový audit“),
- `subtitle` = krátký popis („Vytvořit nový audit systémů řízení“).

`SearchResult` z V1 **nemusí** měnit tvar dat — stačí rozšířit množinu `source_type` a chování `open_result()`.

### Otevření / spuštění akce

U datového objektu `open_result()` otevře **konkrétní záznam** (dialog, stránka s ID).

U výsledku typu `action` se **nez otevírá záznam** — spustí se **definovaná aplikční akce**:

| Kategorie akce | Příklad |
|----------------|---------|
| Otevřít modul | přejít na Dashboard, Úkoly, Audity |
| Otevřít dialog | Nový audit, Nová prověrka, Nový úraz |
| Vytvořit nový záznam | `page.new_audit()`, `page.new_task()` |
| Systémová operace | záloha / obnova databáze |
| Otevřít nástroj | Manažer auditů, editor metodiky |

Navrhované rozhraní (budoucí):

```python
class SearchAction(Protocol):
    action_key: str
    title: str
    keywords: tuple[str, ...]

    def execute(self, host) -> bool: ...
```

Agregátor nebo `ActionSearchProvider` vrací `SearchResult(source_type="action", …)` a `open_result()` deleguje na `ActionRegistry.execute(action_key, host)`.

### Architektura Command Palette (náčrt)

```
GlobalSearchService.search()
    ├── DataSearchProvider(s)     → task, audit, finding, …
    └── ActionSearchProvider      → action (příkazy aplikace)
```

Obě větve sdílejí stejný dialog a stejný model `SearchResult` — liší se pouze `source_type` a chování po Enter.

### UI Command Palette

Budoucí UI vychází z dialogu globálního vyhledávání (Commit 3), ale vizuálně a chováním se blíží **Command Palette**:

- **Klávesová zkratka Ctrl+K** — primární vstup (jednotné s moderními aplikacemi).
- **Dialog přes celou šířku** nahoře uprostřed obrazovky (overlay), ne malé pole v toolbaru.
- **Okamžité filtrování** při psaní — bez nutnosti potvrzovat dotaz.
- **Výsledky ve třech skupinách** (volitelně s nadpisy):
  - **Data** — nalezené záznamy (úkoly, audity, úrazy…),
  - **Akce** — spustitelné příkazy,
  - **Moduly** — rychlý přechod do modulu aplikace.
- **Ikony podle typu výsledku** — úkol, audit, prověrka, akce (+), modul (složka) atd.; konzistentní s ikonografií sidebaru.
- **Enter** = otevřít záznam nebo spustit akci; **Esc** = zavřít paletu.

Pořadí skupin: nejdříve **Akce** (přesná shoda s příkazem), pak **Data**, pak **Moduly** — nebo podle relevance skóre.

### Vztah k implementačnímu plánu V1

| Fáze | Obsah |
|------|--------|
| Commit 1–6 | Globální vyhledávání **dat** (V1) |
| Commit 7+ (budoucí) | `ActionSearchProvider`, registr akcí, Command Palette UI |

V1 musí být navržena tak, aby Command Palette **nepožadovala přepis** — pouze doplnění providera akcí a rozšíření `open_result()` o větev `action`.

---

## Výkon

### V1 — jednoduché dotazy

- **LIKE** `%term%` nad SQLite sloupci.
- Načtení seznamů přes existující service metody tam, kde dat objem malý.
- Globální **limit 30** výsledků (konfigurovatelný).
- Minimální délka dotazu **2 znaky**.

### Budoucí rozšíření (mimo V1)

| Možnost | Popis |
|---------|--------|
| **SQLite FTS5** | Virtuální tabulka `search_index`, trigery při INSERT/UPDATE |
| **Indexování na pozadí** | Worker / job po startu aplikace nebo po změně dat |
| **Relevance score** | `bm25()` ve FTS5 nebo vlastní váhy polí |
| **Inkrementální index** | Per-modul indexy sloučené agregátorem |
| **Cache posledního dotazu** | Krátkodobá cache pro opakované hledání |
| **Command Palette** | Akce aplikace vedle datových výsledků — viz kapitola výše |

Dokumentace implementace FTS patří do samostatného addenda po dokončení V1.

---

## Bezpečnost a robustnost

### Izolace providerů

```python
for provider in self._providers:
    try:
        results.extend(provider.search(query, limit=limit))
    except Exception:
        logger.exception("Search provider %s failed", provider.provider_key)
        continue
```

- Jeden padlý modul **nesmí** vrátit prázdnou obrazovku celé aplikaci.
- Chyba se **zaloguje** (`logging.exception`), uživateli se zobrazí jen výsledky ostatních modulů.
- V debug režimu volitelně indikátor „část modulů nedostupná“.

### Validace vstupu

- Ořezat whitespace, omezit max. délku dotazu (např. 200 znaků).
- Escapovat `%` a `_` pro LIKE, nebo používat parametrizované dotazy.

### Otevírání

- Před otevřením ověřit, že `source_id` existuje; jinak `QMessageBox` s informací „Záznam nebyl nalezen“.
- `open_result` vrací `bool` — UI podle toho reaguje.

---

## Závislosti a hranice modulů

| Vrstva | Smí importovat |
|--------|----------------|
| `core/search/providers/*` | `core/*`, `moduly/*/sluzby`, `moduly/*/repository` |
| `core/search/global_search_service` | providery, modely, `SourceNavigator` (pro open) |
| Moduly | **ne** importují `global_search_service` zpětně |
| UI hlavního okna | pouze `global_search_service` |

Moduly **nemusí** vědět o globálním vyhledávání — stačí, že jejich service/repository umí vrátit data pro provider.

---

## Implementační plán commitů

| Commit | Obsah |
|--------|--------|
| **Commit 1** | Tento architektonický dokument (`dokumentace/GLOBALNI_VYHLEDAVANI.md`) |
| **Commit 2** | Datové třídy (`SearchResult`, konstanty), refaktor `GlobalSearchService` na agregátor, rozhraní `SearchProvider`, první provider — **Úkoly** |
| **Commit 3** | UI dialog vyhledávání (`GlobalSearchDialog`), seskupení podle modulů, navigace klávesnicí |
| **Commit 4** | `open_result()` / `SearchResultOpener`, napojení na stránky modulů a dialogy |
| **Commit 5** | Další providery: **Audity**, **Program auditů**, **Zjištění**, **Prověrky**, **Kniha úrazů**, **Pracoviště**, **THP** |
| **Commit 6** | Integrace do hlavního okna, klávesová zkratka Ctrl+K / Ctrl+F, vylepšení toolbar completeru |
| **Commit 7+** (budoucí) | Command Palette — `ActionSearchProvider`, registr akcí, skupiny Data / Akce / Moduly |

Každý commit = malý reviewovatelný diff, testy u providerů a otevírání.

---

## Testování (orientačně pro další commity)

- Unit testy providerů s izolovanou test DB.
- Test agregátoru: sloučení, limit, řazení, odolnost proti výjimce providera.
- Test `open_result` s mock `host` / stránkami modulů.
- Integrační test: dotaz → výsledek → otevření dialogu (offscreen Qt).

---

## Shrnutí

Globální vyhledávání BOZP 3.0 stojí na **jednom agregátoru** a **více tenkých providerech**. `SearchResult` s `source_type` + `source_id` umožní jednotné zobrazení i otevírání. V1 používá jednoduché LIKE dotazy; FTS5 a relevance přijdou později. Provider nesmí shodit celé hledání. UI dialog a zkratky přijdou až po stabilní službě a prvních providerech. **Budoucí Command Palette** rozšíří stejný model o typ `action` a spouštění aplikčních příkazů bez přepisu V1.

**Schválením tohoto dokumentu se spouští Commit 2.**
