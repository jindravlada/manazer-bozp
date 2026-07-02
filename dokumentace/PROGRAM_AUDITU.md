# Manažer auditů / Program auditů — architektura

> **Commit 1 — návrhový dokument**
>
> Tento dokument popisuje architekturu a workflow modulu **Manažer auditů** a entity **Program auditů**.
> Neobsahuje implementaci databáze, UI ani konkrétní kód.
> Slouží jako schvalovací podklad pro následnou implementaci po malých commitech.

---

## Názvosloví

| Pojem | Význam |
|-------|--------|
| **Manažer auditů** | Pracovní část modulu, která řídí celý proces interního auditování — plánování, provádění, sledování plnění a uzavření auditního cyklu. |
| **Program auditů** | Konkrétní auditní program / auditní cyklus organizace, např. *1. 4. 2026 – 31. 3. 2029*. Odpovídá pojmu *audit program* dle ISO 19011. |
| **Audit** | Jedna konkrétní realizace auditu na konkrétním pracovišti v rámci Programu auditů. |
| **Řídicí proces** | Oblast řízení organizace, která se audituje (evidence v metodice auditora, registr `procesy.json` + JSON soubory procesů). |
| **Návštěva** | Plánovaný termín auditu na pracovišti v konkrétním měsíci cyklu; může být realizována jedním nebo více audity. |
| **Norma / systém řízení** | Standard, jehož požadavky se v rámci auditu ověřují (ISO 45001, ISO 9001, později ISO 14001). |

---

## 1. Účel Manažera auditů a Programu auditů

### Co řeší

Manažer auditů sjednocuje celý životní cyklus interních auditů systémů řízení v organizaci:

- plánování auditního cyklu na období (Program auditů),
- výběr auditovaných pracovišť a rozložení návštěv v čase,
- rozdělení řídicích procesů mezi návštěvy a pracoviště,
- vytváření a provádění jednotlivých auditů,
- sledování plnění programu v průběhu cyklu,
- propojení se zjištěními, úkoly a historií pracoviště.

### Proč vzniká

Současný modul **Audity systémů řízení** eviduje jednotlivé audity a metodiku auditora, ale neřídí **program auditů** jako celek. Chybí:

- plán na celý auditní cyklus,
- přehled, které řídicí procesy už byly na pracovišti auditovány a které zbývají,
- automatické generování návštěv a rozdělení procesů,
- statistiky plnění programu podle pracovišť, procesů a norem.

Manažer auditů doplňuje existující modul auditů o vrstvu **programového řízení** bez duplicity evidence samotného auditu.

### Program auditů × Audit

| | **Program auditů** | **Audit** |
|---|-------------------|-----------|
| **Úroveň** | Strategický plán na období | Operativní realizace |
| **Rozsah** | Celá organizace, všechna pracoviště a procesy cyklu | Jedno pracoviště, konkrétní návštěva / termín |
| **Trvání** | Měsíce až roky (např. 3letý cyklus) | Hodiny až dny |
| **Výstup** | Schválený plán návštěv a procesů | Protokol auditu, zjištění, úkoly |
| **Stav** | Příprava → Schválení → Provádění → Uzavření | Plánováno → Probíhá → Dokončeno |

**Program auditů** odpovídá plánu *co, kde, kdy a v jakém rozsahu* se bude auditovat.

**Audit** je konkrétní exekuce tohoto plánu na pracovišti s využitím metodiky auditora.

### Proč pojem Program auditů podle ISO 19011

Norma **ISO 19011** (Směrnice pro auditování systémů managementu) používá pojem **audit program** jako souhrn plánovaných auditů vztahujících se k určitému cíli. Program auditů v Manažeru BOZP:

- respektuje principy ISO 19011 (plánování, provádění, vyhodnocování, zlepšování),
- není vázán pouze na ISO 45001 — podporuje integrované audity více systémů řízení,
- odděluje **programové plánování** od **jednotlivého auditu**, což odpovídá běžné praxi interních auditorů a požadavkům certifikačních auditů.

---

## 2. Rozsah norem

### Aktuální rozsah v1

První implementace Manažera auditů je určena pro **integrovaný program auditů BOZP + kvalita**:

- **ISO 45001** — systém managementu BOZP,
- **ISO 9001** — systém managementu kvality.

Program auditů, plánované řídicí procesy i statistiky musí umožnit filtrovat a vyhodnocovat plnění podle obou norem současně i samostatně.

### Budoucí připravenost — ISO 14001 / EMS

**EMS / ISO 14001** není součástí první implementace (řešeno mimo aplikaci), ale architektura musí být navržena tak, aby doplnění EMS nevyžadovalo zásadní přestavbu:

- rozsah norem je **seznam hodnot**, ne pevně zakódovaná dvojice polí,
- každý řídicí proces nese vazbu na **jednu nebo více norem** (již existuje v metodice jako `pozadavky_norem`),
- statistiky a filtry pracují s obecným pojmem **norma / systém řízení**,
- metadata Programu auditů obsahují volitelný rozsah norem včetně rezervy pro ISO 14001.

Princip rozšíření: přidání ISO 14001 = doplnění hodnoty do číselníku norem + aktivace v rozsahu programu + doplnění vazeb u procesů. Bez změny workflow ani entity modelu.

---

## 3. Životní cyklus Programu auditů

```
Nový Program
     ↓
Příprava
     ↓
Výběr auditovaných pracovišť
     ↓
Generování návštěv podle měsíců
     ↓
Rozdělení řídicích procesů
     ↓
Ruční úpravy
     ↓
Schválení
     ↓
Provádění auditů
     ↓
Sledování plnění
     ↓
Uzavření programu
     ↓
Nový auditní cyklus
```

### Popis fází

| Fáze | Popis |
|------|-------|
| **Nový Program** | Uživatel založí nový Program auditů s názvem, obdobím a rozsahem norem. |
| **Příprava** | Program je ve stavu editace — lze měnit metadata, pracoviště, návštěvy i procesy. |
| **Výběr auditovaných pracovišť** | Automaticky nebo ručně se vyberou pracoviště s příznakem *Auditovat = Ano*. |
| **Generování návštěv** | Systém vytvoří návštěvy podle období programu, intervalu pracoviště a zvolených měsíců. |
| **Rozdělení řídicích procesů** | Aktivní řídicí procesy z metodiky se rozdělí mezi návštěvy pracoviště v cyklu. |
| **Ruční úpravy** | Auditor / koordinátor upraví termíny, přesune procesy, přidá nebo vyjme návštěvy. |
| **Schválení** | Program přejde do stavu *Schválený* — plán je závazný, ale stále umožňuje řízené výjimky. |
| **Provádění auditů** | Z návštěv se vytvářejí audity; auditor pracuje v existujícím dialogu auditu. |
| **Sledování plnění** | Přehled % splnění, zbývajících procesů, otevřených zjištění a úkolů. |
| **Uzavření programu** | Po dokončení cyklu nebo na konci období se program uzavře; neuzavřené položky jsou viditelné. |
| **Nový auditní cyklus** | Založení navazujícího Programu auditů (typicky s přenesením neuzavřených položek do přehledu). |

### Stavy Programu auditů (návrh)

| Stav | Význam |
|------|--------|
| `priprava` | Editace, generování, ruční úpravy |
| `schvaleny` | Plán schválen, probíhá realizace |
| `provadeni` | Alias nebo podstav — aktivní fáze auditů (volitelně sloučit se *schválený*) |
| `uzavreny` | Cyklus ukončen |
| `zruseny` | Program zrušen bez dokončení (výjimečný stav) |

> **Poznámka k implementaci:** přesná množina stavů a přechodů bude upřesněna v implementační fázi; workflow výše je architektonický rámec.

---

## 4. Hlavní entity a vazby

### Přehled entit

```
┌─────────────────────┐
│   Program auditů    │
│  (auditní cyklus)   │
└─────────┬───────────┘
          │ 1
          │
          │ N
┌─────────▼───────────┐       ┌──────────────────┐
│      Návštěva       │──N:1──│    Pracoviště    │
│  (plán na měsíc)    │       │  (číselník)      │
└─────────┬───────────┘       └──────────────────┘
          │ 1
          │
          │ 0..1
┌─────────▼───────────┐
│       Audit         │───────┐
│   (realizace)       │       │
└─────────┬───────────┘       │
          │                   │
          │ N                 │ vazba na
┌─────────▼───────────┐       │ existující
│ Plánovaný řídicí    │       │ modul Audity
│      proces         │       │
└─────────┬───────────┘       │
          │                   │
          │ N:M               │
┌─────────▼───────────┐       │
│  Norma / systém     │       │
│     řízení          │       │
└─────────────────────┘       │
                              │
          ┌───────────────────┘
          │
┌─────────▼───────────┐     ┌──────────────┐
│     Zjištění        │─────│    Úkol      │
│  (Finding)          │     │   (Task)     │
└─────────────────────┘     └──────────────┘
```

### Entity — stručný popis

| Entita | Popis | Vazby |
|--------|-------|-------|
| **Program auditů** | Kořenový plán auditního cyklu | → Návštěvy, metadata norem |
| **Pracoviště** | Fyzické / organizační místo auditu (číselník Nastavení) | → Návštěvy, historie auditů |
| **Návštěva** | Plánovaný termín auditu na pracovišti (měsíc/rok) | → Program, Pracoviště, Plánované procesy, Audit |
| **Řídicí proces** | Proces z metodiky auditora (`procesy.json`) | → Plánované procesy v návštěvách, normy |
| **Norma / systém řízení** | ISO 45001, ISO 9001, (ISO 14001) | → Program (rozsah), Plánovaný proces |
| **Plánovaný řídicí proces** | Konkrétní proces v plánu návštěvy | → Návštěva, Řídicí proces, Normy, Audit (po splnění) |
| **Audit** | Realizace auditu (existující entita) | → Návštěva, Pracoviště, Zjištění, Úkoly |
| **Zjištění** | Finding navázaný na audit (sdílená entita) | → Audit |
| **Úkol** | Task navázaný na zjištění / audit | → Zjištění, Audit |

### Klíčové vazby

1. **Program auditů → Návštěvy** — program obsahuje všechny plánované návštěvy cyklu.
2. **Návštěva → Pracoviště** — každá návštěva je vždy na jednom pracovišti.
3. **Návštěva → Plánované řídicí procesy** — seznam procesů, které má auditor na návštěvě ověřit.
4. **Plánovaný proces → Normy** — které systémy řízení proces na této návštěvě pokrývá.
5. **Návštěva → Audit** — po zahájení auditu se návštěva propojí s konkrétním auditním spisem (0..1 v plánu, 1 po vytvoření).
6. **Audit → Zjištění / Úkoly** — stávající mechanismus modulu Audity beze změny principu.
7. **Plánovaný proces → Audit** — po dokončení auditu proces získá vazbu na audit, kterým byl splněn.

---

## 5. Program auditů — metadata

| Pole | Typ | Popis |
|------|-----|-------|
| `id` | identifikátor | Interní ID programu |
| `nazev` | text | Název programu, např. *Interní audity 2026–2029* |
| `datum_od` | datum | Začátek auditního cyklu (např. 1. 4. 2026) |
| `datum_do` | datum | Konec auditního cyklu (např. 31. 3. 2029) |
| `stav` | enum | `priprava` / `schvaleny` / `uzavreny` / … |
| `rozsah_norem` | seznam | Aktivní normy: `ISO 45001`, `ISO 9001`; do budoucna `ISO 14001` |
| `popis` | text | Stručný popis účelu programu |
| `poznamka` | text | Interní poznámka koordinátora |
| `datum_vytvoreni` | datetime | Kdy byl program založen |
| `autor` | text / vazba | Kdo program vytvořil |
| `datum_schvaleni` | datetime | Kdy byl program schválen (volitelné) |
| `schvalil` | text / vazba | Kdo program schválil (volitelné) |

### Odvozené / agregované hodnoty (neukládat duplicitně)

- počet návštěv,
- počet splněných / zbývajících procesů,
- % plnění programu,
- počet neuzavřených zjištění a otevřených úkolů v rámci programu.

Agregace se počítají za běhu ze stavu návštěv, plánovaných procesů a navázaných auditů.

---

## 6. Pracoviště

### Zdroj dat

Program auditů pracuje s pracovišti z číselníku **Nastavení → Pracoviště** (existující entita `Workplace`).

### Příznak Auditovat

Do číselníku pracovišť se doplní (v implementační fázi) příznak:

| Pole | Hodnoty | Význam |
|------|---------|--------|
| `auditovat` | Ano / Ne | Zda je pracoviště zařazeno do interních auditů |

**Pravidlo:** automatické generování programu vybírá pouze pracoviště s `auditovat = Ano` a `active = True`.

### Interval auditu pracoviště

Některá pracoviště nejsou auditována stejně často. Návrh doplňkových polí:

| Pole | Typ | Popis |
|------|-----|-------|
| `audit_interval_mesicu` | celé číslo | Požadovaný interval mezi návštěvami (např. 6, 12, 24) |
| `audit_poznamka` | text | Důvod odlišného intervalu (volitelné) |

**Příklad:**

- centrála — interval 12 měsíců,
- provoz A — interval 6 měsíců,
- sklad — interval 24 měsíců.

Generátor návštěv respektuje interval pracoviště v rámci období programu.

### Pracoviště mimo program

Pracoviště s `auditovat = Ne` se do programu negenerují, ale lze je ručně přidat (mimořádný audit / výjimka) — v takovém případě systém upozorní, že jde o nestandardní zařazení.

---

## 7. Návštěvy

Návštěva je **plánovaný termín auditu** na pracovišti. Není vázána na pevný model jaro/podzim — měsíce jsou plně konfigurovatelné.

### Metadata návštěvy

| Pole | Typ | Popis |
|------|-----|-------|
| `id` | identifikátor | Interní ID návštěvy |
| `program_id` | vazba | Program auditů |
| `pracoviste_id` | vazba | Pracoviště |
| `mesic` | 1–12 | Plánovaný měsíc |
| `rok` | celé číslo | Plánovaný rok |
| `planovane_datum` | datum | Konkrétní plánované datum (volitelné, upřesnění) |
| `stav` | enum | `planovana` / `probehla` / `zrusena` / `presunuta` |
| `audit_id` | vazba | Navázaný audit po vytvoření (null dokud neexistuje) |
| `poznamka` | text | Poznámka koordinátora / auditora |

### Příklad cyklu

Program: **1. 4. 2026 – 31. 3. 2029** (36 měsíců)

Pracoviště *Provoz Gamma*, interval 12 měsíců:

| Návštěva | Měsíc/rok | Plánované datum |
|----------|-----------|-----------------|
| 1 | duben 2026 | 15. 4. 2026 |
| 2 | duben 2027 | 20. 4. 2027 |
| 3 | duben 2028 | 10. 4. 2028 |

Pracoviště *Sklad Praha*, interval 6 měsíců — 6 návštěv v cyklu atd.

### Vztah návštěva ↔ audit

- V plánovací fázi existuje návštěva **bez auditu**.
- Akce *Vytvořit audit z návštěvy* vytvoří auditní spis s předvyplněným pracovištěm, měsícem a plánovanými procesy.
- Po dokončení auditu se stav návštěvy aktualizuje na *proběhla*.

---

## 8. Řídicí procesy v programu

### Zdroj procesů

Seznam řídicích procesů vychází z **metodiky auditora** (registr `procesy.json`, aktivní procesy). Program auditů nekopíruje metodický obsah — pracuje pouze s identifikátory a metadaty procesů.

### Plánovaný řídicí proces

Entita navazující návštěvu na řídicí proces:

| Pole | Typ | Popis |
|------|-----|-------|
| `id` | identifikátor | Interní ID |
| `navsteva_id` | vazba | Návštěva |
| `proces_id` | text | ID řídicího procesu z metodiky |
| `normy` | seznam | Normy, které tento proces na návštěvě pokrývá (`ISO 45001`, `ISO 9001`, …) |
| `stav` | enum | `planovany` / `splneny` / `presunuty` / `zruseny` |
| `audit_id` | vazba | Audit, kterým byl proces splněn (null do dokončení) |
| `poznamka` | text | Poznámka (důvod přesunu apod.) |

### Vazba na normy

Každý řídicí proces v metodice nese požadavky norem (`pozadavky_norem`). Při generování programu:

1. systém načte aktivní procesy,
2. pro každý proces určí relevantní normy z metodiky,
3. filtruje podle `rozsah_norem` programu,
4. přiřadí proces do návštěvy.

Jeden proces může být v cyklu plánován **vícekrát** (různá pracoviště), ale na **jedné návštěvě** je každý proces nejvýše jednou.

### Po dokončení auditu

1. Auditor dokončí audit v existujícím dialogu auditu.
2. Systém označí všechny **plánované procesy** dané návštěvy, které byly v auditu skutečně auditovány, jako `splneny`.
3. Plánovaný proces získá vazbu `audit_id`.
4. Program přepočítá statistiky zbývajících procesů v cyklu.

> **Upřesnění v implementaci:** mapování „proces auditován v auditu" vychází ze stávající záložky Řídicí procesy v dialogu auditu (vazba na `control_result` / výsledky ověření).

---

## 9. Historie pracoviště

Při zahájení auditu (nebo při otevření návštěvy) auditor vidí **kontext pracoviště**:

| Přehled | Zdroj |
|---------|-------|
| Poslední audit pracoviště | Audity se stejným `workplace_id`, seřazené dle data |
| Neuzavřená zjištění | Findings z auditů pracoviště se stavem ≠ Vypořádáno |
| Otevřené úkoly | Tasks navázané na zjištění z auditů pracoviště |
| Historie auditů | Seznam všech auditů na pracovišti v rámci programu i mimo něj |
| Historie auditovaných řídicích procesů | Plánované procesy + dokončené audity na pracovišti |

### Cíl

Auditor okamžitě vidí:

- co bylo na pracovišti zjištěno minule,
- jak organizace postupovala při nápravě,
- které procesy v aktuálním cyklu ještě nebyly auditovány.

Historie pracoviště je **agregace existujících dat** (audity, zjištění, úkoly, plánované procesy) — ne samostatná entita.

---

## 10. Automatika

### Generovat program

Hlavní akce v přípravné fázi Programu auditů. Spustí sekvenci kroků 10.2–10.4. Existující ruční úpravy v programu jsou před regenerací potvrzeny (varování před přepsáním).

### Automatický výběr auditovaných pracovišť

```
Všechna pracoviště WHERE auditovat = Ano AND active = True
```

Volitelně: filtr podle organizační jednotky (backlog).

### Automatické vytvoření návštěv

Pro každé vybrané pracoviště:

1. načti `audit_interval_mesicu` (výchozí např. 12),
2. od `datum_od` programu generuj termíny až do `datum_do`,
3. pro každý termín vytvoř návštěvu s `mesic`, `rok`, stav `planovana`.

Měsíce nejsou pevné — respektují interval a začátek cyklu.

### Automatické rozdělení řídicích procesů

Pro každé pracoviště v cyklu:

1. načti aktivní řídicí procesy z metodiky,
2. filtruj podle `rozsah_norem` programu,
3. rozděl procesy rovnoměrně mezi návštěvy pracoviště (např. N procesů / M návštěv),
4. u každého plánovaného procesu nastav `normy` dle metodiky.

**Princip rozdělení:** všechny procesy musí být v cyklu pokryty alespoň jednou; preferuje se rovnoměrné zatížení návštěv.

### Ruční úpravy vygenerovaného programu

Po generování koordinátor může:

- přesunout návštěvu na jiný měsíc,
- sloučit / rozdělit návštěvy,
- přidat nebo odebrat plánovaný proces,
- změnit vazbu procesu na normu,
- vyjmout pracoviště z programu.

Změny jsou povoleny ve stavu `priprava` bez omezení; ve stavu `schvaleny` s auditní stopou (implementační detail).

### Automatické vytvoření auditu z návštěvy

Akce *Vytvořit audit*:

1. vytvoří auditní spis (existující entita `Audit`),
2. předvyplní `workplace_id`, `planned_month`, `year`, `title`,
3. propojí `navsteva.audit_id`,
4. předá seznam plánovaných procesů do dialogu auditu.

### Automatické označení plánovaného procesu jako splněného

Po přechodu auditu do stavu **Dokončeno**:

- plánované procesy návštěvy, které byly v auditu ověřeny, → `splneny` + vazba `audit_id`,
- návštěva → `probehla`.

### Automatické sledování zbývajících procesů v cyklu

Program průběžně počítá:

- celkový počet plánovaných procesů v programu,
- počet splněných,
- seznam nesplněných procesů po pracovištích a normách,
- varování při blížícím se konci cyklu s neuzavřenými procesy.

---

## 11. Statistiky

Přehledy v rámci Programu auditů (a filtrovaně na pracoviště / normu):

| Přehled | Popis |
|---------|-------|
| **% splnění programu** | `splněné plánované procesy / celkem plánovaných procesů × 100` |
| **Splnění po pracovištích** | Tabulka pracovišť s % a počty splněných / zbývajících procesů |
| **Splnění po řídicích procesech** | Které procesy jsou v cyklu již pokryty a kde ještě chybí |
| **Splnění podle norem** | ISO 45001 / ISO 9001 — oddělené % pokrytí |
| **Zbývající procesy** | Seznam nesplněných plánovaných procesů s pracovištěm a plánovanou návštěvou |
| **Neuzavřená zjištění** | Findings z auditů programu se stavem ≠ Vypořádáno |
| **Otevřené úkoly** | Tasks navázané na zjištění z auditů programu |

Statistiky jsou **odvozené** — neukládají se jako samostatná data, počítají se z návštěv, plánovaných procesů, auditů, zjištění a úkolů.

---

## 12. Vztah k existujícímu modulu Audity

Manažer auditů **nepřepisuje** stávající funkcionalitu:

| Existující | Role v nové architektuře |
|------------|-------------------------|
| Dialog auditu | Realizace jednoho auditu |
| Metodika auditora | Zdroj řídicích procesů a norem |
| Zjištění (Finding) | Výstup auditu, sledování nápravy |
| Úkoly (Task) | Nápravná opatření |
| Tabulka auditů | Seznam realizací; doplněna o vazbu na Program / Návštěvu |

Nová vrstva **Program auditů** stojí nad evidencí auditů a propojuje plánování s realizací.

---

## 13. Architektonické vrstvy (implementační orientace)

> Tato kapitola popisuje směr pro budoucí commity — **ne závaz k okamžité implementaci**.

```
UI (Manažer auditů)
    ↓
Služby (program_service, navsteva_service, generator_service, statistiky_service)
    ↓
Repository (program, navsteva, planovany_proces)
    ↓
Modely (ProgramAuditu, Navsteva, PlanovanyRidiciProces)
    ↓
Existující: Audit, Workplace, Finding, Task, audit_knowledge_service
```

Modul zůstane v `moduly/audity/` s novými podkomponentami pro program auditů, aby nedocházelo k roztříštění auditní domény.

---

## 14. Backlog — mimo první verzi

Následující funkce **nejsou součástí první implementace** (v1):

- kalendář (vizuální plánování návštěv v kalendáři),
- import programu (Excel, CSV),
- export programu (PDF, Excel),
- drag & drop (přesouvání návštěv a procesů myší),
- dashboard (souhrnný panel napříč moduly),
- notifikace (e-mail / upozornění na blížící se termíny),
- EMS / ISO 14001 (plná integrace do programu),
- automatické návrhy podle rizikovosti pracoviště,
- pokročilé priority auditů,
- historie změn programu (audit trail plánu).

---

## Schvalovací checklist

- [ ] Názvosloví odpovídá ISO 19011 a praxi organizace
- [ ] Rozsah v1 (ISO 45001 + ISO 9001) je dostačující
- [ ] Workflow cyklu programu odpovídá reálnému procesu
- [ ] Entity a vazby pokrývají plánování i realizaci
- [ ] Automatika generování je akceptovatelná
- [ ] Historie pracoviště poskytuje auditorovi potřebný kontext
- [ ] Backlog v1 je správně vymezen

Po schválení tohoto dokumentu začne implementace po malých commitech (datový model → služby → generátor → UI).
