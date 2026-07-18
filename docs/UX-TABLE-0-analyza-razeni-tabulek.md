# UX-TABLE-0 – Analýza řazení tabulek

Stav k 2026-07-18. Pouze podklad pro další fáze UX-TABLE. **Bez změny chování.**

## Shrnutí verdiktu

| Otázka | Odpověď |
|--------|---------|
| Existuje společné UI řešení pro řazení klikem na hlavičku? | **Ne.** |
| Existuje české porovnávání textů? | **Ano** – `core/utils/czech_sort.py` (Python klíč), ale **ne** napojené na hlavičky tabulek. |
| `QSortFilterProxyModel` / `QCollator` / `localeAwareCompare`? | **Nenalezeno** v aplikačním kódu (`core/`, `moduly/`). |
| Ukládání zvoleného sloupce a směru řazení? | **Nenalezeno.** |
| Kde je `setSortingEnabled(True)`? | **Jen Audity → Program auditů → dashboard** (zjištění + úkoly). |

---

## 1. Kde už je řazení použité

### 1.1 Interaktivní řazení kliknutím na hlavičku

Jediné místo v projektu:

| Soubor | Tabulky |
|--------|---------|
| `moduly/audity/ui/audit_program_dashboard_widget.py` | Zjištění programu, Úkoly programu |

- `_build_table()` volá `table.setSortingEnabled(True)`.
- Při plnění se sorting dočasně vypne (`False` → naplnění → `True`).
- Žádné `sortByColumn` / `sortItems` / `sectionClicked` handler pro řazení jinde v aplikaci.

### 1.2 Příprava dat pro řazení (bez zapnutého sorting)

| Soubor | Poznámka |
|--------|----------|
| `moduly/audity/ui/audit_program_planned_visits_widget.py` | Do buněk termínu ukládá `_SORT_ROLE = Qt.UserRole + 1` (`toordinal()`), ale **`setSortingEnabled` se nevolá** – řádky přicházejí už seřazené ze služby. |

### 1.3 Server-/service-side pevné pořadí (bez klikací hlavičky)

Typický vzor hlavních seznamů: načti z DB / service → naplň `QTableWidget` → žádné UI sorting.

| Modul | Hlavní tabulka | Zdroj pořadí |
|-------|----------------|--------------|
| Úkoly | `moduly/ukoly/ui/task_table.py` | SQL: `completed`, `due_date`, `id` |
| Audity | `moduly/audity/ui/audit_table.py` | SQL: `audit_date.desc()`, `id.desc()` |
| Prověrky | `moduly/proverky/ui/bozp_inspection_table.py` | SQL: `inspection_date.desc()`, `id.desc()` |
| Vyšetřování MU | `moduly/vysetrovani_mu/ui/mu_investigation_table.py` | SQL: `started_at.desc()`, `id.desc()` |
| Kniha úrazů | `moduly/kniha_urazu/ui/accident_table.py` | SQL: `year.desc()`, `id.desc()` |
| Registr právních požadavků | `moduly/pravni_pozadavky/ui/legal_requirement_table.py` | SQL: `active.desc()`, `next_verification_date`, `regulation_name`, `id` |
| Identifikace rizik | `moduly/rizeni_rizik/ui/hazard_identification_table.py` | SQL: `started_at.desc()`, `id.desc()` |
| Katalog zdrojů rizik | `hazard_library_page.py` | `czech_sorted` podle názvu v service |

`core/widgets/table_utils.py` řeší jen šířky / resize módy sloupců, **ne řazení**.

### 1.4 České řazení mimo tabulky (combo / číselníky / služby)

`core/utils/czech_sort.py` je aktivně používané, ale jako **příprava seznamů**, ne jako Qt table sorter:

- Selectory: `person_selector`, `thp_worker_selector`, `workplace_selector`, `responsibility_role_selector`, `exposed_group_selector`
- Nastavení: repository / workplace hierarchy
- Kniha úrazů: `ciselnik_service`, NACE/osoby v záložce zapisovatele
- Registr: `czech_sorted` pro filtr vlastníků; procesy řadí `process_code_sort_key`
- Řízení rizik: více services (`hazard_*`) + working copy

Doménové klíče (ne `czech_sort`):

- `process_code_sort_key` – `moduly/pravni_pozadavky/constants.py`
- `visit_sort_key` – Audity program návštěv
- `mu_number_sort_key` – Vyšetřování MU
- chronologie v Knize úrazů / MU

---

## 2. Jak je technicky řešené

### 2.1 České porovnání textů (`czech_sort`)

Soubor: `core/utils/czech_sort.py`  
Export: `core/utils/__init__.py`

| Funkce | Účel |
|--------|------|
| `czech_sort_key(value)` | Porovnatelný klíč: česká abeceda včetně **CH za H**, diakritika (Č/Š/Ž…), **natural split** číslic (`re.split(r"(\d+)"`) → čísla jako `int`) |
| `czech_sorted(items, key=…)` | Obálka nad `sorted` |
| `person_display_name_sort_key` | Odstraní tituly, řadí podle příjmení |
| `worker_sort_key` | THP: `last_name` + `first_name` (s fallbacky) |

Implementace je **čistě Python** (NFC + vlastní mapa pořadí písmen). Nejde o Qt `QCollator`.

**Testy:** v `tests/` **neexistují** dedicated testy `czech_sort`.

### 2.2 Interaktivní tabulka (Audity dashboard)

```text
QTableWidget
  + setSortingEnabled(True)
  + buňky = QTableWidgetItem(display_text)
  + u sloupce Termín volitelně setData(UserRole+1, date.toordinal())
```

- **Není** `setSortRole(_SORT_ROLE)`.
- Qt tedy při kliknutí řadí podle **DisplayRole** (zobrazený text), ne podle ordinal.
- Důsledek: datum `"15.06.2026"` se řadí lexikograficky jako řetězec `dd.mm.yyyy`, nikoli chronologicky; prázdné termíny jsou `"—"`; `_SORT_ROLE` je připravené, ale **nenapojené**.

### 2.3 Co v projektu chybí

| Mechanismus | Stav |
|-------------|------|
| `QSortFilterProxyModel` | Ne |
| `QCollator` / `localeAwareCompare` | Ne |
| Vlastní `lessThan` / proxy | Ne |
| Společný helper „enable Czech sorting on table“ | Ne |
| Persistace sloupce + směru (QSettings / DB) | Ne |
| `header.saveState` / `restoreState` pro sort | Ne |

`core/models/` obsahuje jen `attachment` – žádný table/sort model.

---

## 3. Zda správně respektuje češtinu

| Kontext | Čeština |
|---------|---------|
| `czech_sort` / `czech_sorted` | Ano – vlastní abeceda včetně CH; vhodné pro názvy osob, pracovišť, číselníků. |
| Selectory a service listy používající `czech_sorted` | Ano (pokud klíč bere správný text). |
| Interaktivní `setSortingEnabled` (Audity dashboard) | **Ne** – výchozí Qt porovnání DisplayRole (typicky unicode / locale systému, **ne** projektový český klíč, **ne** CH jako jedno písmeno). |
| SQL `ORDER BY regulation_name` apod. | Záleží na SQLite collation – **není** zaručené české řazení. |
| `.casefold()` / `.lower()` v search providers | Není české abecední řazení (jen normalizace pro skóre/dedup). |

---

## 4. Schopnost správně řadit typy hodnot

Hodnocení vůči **cíli** společného UI řazení (klik na hlavičku):

| Typ | `czech_sort` (Python) | Audity dashboard (`setSortingEnabled`) | Typické SQL ORDER BY |
|-----|----------------------|----------------------------------------|----------------------|
| Text (jména, názvy) | Ano (CZ abeceda + CH) | Ne (neprojektové CZ) | Spíš ne |
| Čísla v textu (`2` vs `10`) | Ano (natural split) | Ne (lexikograficky) | Ano, pokud sloupec je numerický |
| Datum | Ne (je to textový klíč); služby používají `date`/`toordinal` zvlášť | Ne – řadí `dd.mm.yyyy` jako text; ordinal v `_SORT_ROLE` nepoužit | Ano, pokud sloupec je date |
| Prázdné hodnoty | Prázdný string → začátek; bez jednotné politiky „prázdné dolů“ | `"—"` se řadí jako znak | NULL chování DB |
| Ano/Ne | Lexikograficky po normalizaci (`ano`/`ne`) – použitelné, ale ne special-case | Ano/Ne jako text | — |
| Stavy (Koncept, Probíhá…) | Lexikograficky CZ, **ne** doménové pořadí stavů | Lexikograficky DisplayRole | Obvykle pevné pořadí ze service, ne klik |

**Závěr:** žádné stávající UI řešení nepokrývá spolehlivě všechny typy současně. Nejbližší stavební kámen pro text (+ natural čísla) je `czech_sort_key`; pro data/stavy je potřeba typovaná sort role nebo proxy `lessThan`.

---

## 5. Co lze znovu použít jako společný základ

Doporučený reuse (bez implementace v této fázi):

1. **`czech_sort_key` / `czech_sorted`**  
   Společný český textový (a natural-number) klíč. Vhodný základ pro:
   - sort role v `QTableWidgetItem`, nebo
   - `QSortFilterProxyModel.lessThan` / vlastní collator wrapper.

2. **`person_display_name_sort_key` / `worker_sort_key`**  
   Pro sloupce osob (příjmení před jménem, bez titulů).

3. **Vzor Audity dashboard** (jen jako inspirace UX):
   - `setSortingEnabled` + vypnutí při plnění,
   - záměr ukládat typovaný klíč do `UserRole+1` u datumu  
   → nutno **dopsat** `setSortRole` nebo vlastní porovnání, jinak je to nefunkční stub.

4. **`FilterBar`** (`core/widgets/filter_bar.py`)  
   Není řazení, ale ukazuje společný vzor práce s `QTableWidget` (živý filtr + počty). Budoucí sorting by měl respektovat skryté řádky filtru.

5. **Neměnit / nepoužívat jako „hotové UI sorting“:**
   - `process_code_sort_key`, `visit_sort_key`, `mu_number_sort_key` – doménové, ne obecné,
   - SQL ORDER BY seznamů – výchozí pořadí při otevření, ne uživatelské klikání.

---

## 6. Tabulky s `setSortingEnabled(True)` bez českého porovnávání

Kompletní seznam v aplikačním kódu:

| Tabulka | Soubor | České porovnání? | Typovaný sort key? |
|---------|--------|------------------|--------------------|
| Program auditů – Zjištění | `moduly/audity/ui/audit_program_dashboard_widget.py` | Ne | `_SORT_ROLE` u Termínu **uložen**, ale **nepoužit** (chybí `setSortRole`) |
| Program auditů – Úkoly | stejný soubor | Ne | stejný problém |

Žádná jiná tabulka v Úkolech, Knize úrazů, Registru, Prověrkách, Auditech (hlavní seznam), Identifikacích ani Katalogu nemá `setSortingEnabled(True)`.

---

## Doporučení pro další fáze (jen směr, bez implementace)

1. Zavést **jeden** společný mechanismus (preferovaně proxy / `setSortRole` + typed keys), napojený na `czech_sort_key` pro text.
2. Explicitní politiky: datum, číslo, bool Ano/Ne, prázdné hodnoty, případně katalog stavů.
3. Rozhodnout o persistenci sloupce/směru (dnes 0).
4. Audity dashboard buď napojit na nový společný základ, nebo aspoň zapojit existující `_SORT_ROLE`.
5. Doplnit unit testy pro `czech_sort` (CH, Č/Š/Ž, natural čísla) před plošným použitím v UI.
