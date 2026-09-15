# UX STANDARD č. 003

## Jednotná horní lišta seznamových modulů

Tento dokument je závazný pro pořadí, názvy, seskupení a vzhled tlačítek
v **horní liště seznamů** Manažera BOZP.

Navazuje na:

- `UX_BUTTON_AUDIT_001.md` (inventura skutečných akcí)
- `UX_STANDARD_001.md` (aktivace podle výběru)
- `UI_KOMPONENTY.md`
- `UX_NAZVOSLOVI.md`

**Rozsah:** hlavní seznamy modulů a jejich top-level záložky.  
**Neplatí automaticky** pro spodní lištu editorů (tam platí `UI_KOMPONENTY.md` § 10)
ani pro formulářová tlačítka uvnitř dialogů.

**V této verzi standardu se nemění aplikační kód.**  
Zavádění probíhá později: jeden modul = jeden commit, podle pořadí v levém menu.

---

## 1. Závazná obecná pravidla

1. Lišta obsahuje **jen akce, které modul skutečně má**. Nevynucovat prázdné skupiny.
2. Pořadí skupin je jednotné (§ 3). Uvnitř skupiny je pořadí podle frekvence použití zleva.
3. Aktivaci řídí `UX_STANDARD_001.md`. Tento standard neřeší enablement znovu.
4. Stejný význam akce = stejný text (a případně stejná ikona) napříč aplikací.
5. Text musí odpovídat **významu** akce, ne mechanické unifikaci slov.
6. Filtry (`Zobrazit:`, rok, hledání) zůstávají **vpravo** za `addStretch()`.
7. Nevytvářet rozbalovací menu, které obsahuje jedinou akci.
8. Neslučovat dvě často používané přímé akce jen kvůli úspoře místa.
9. Kontextové menu není povinné; pokud existuje, musí být konzistentní s lištou (§ 9).

---

## 2. Katalog skupin tlačítek

Skutečné akce z auditu se řadí do těchto skupin.

### A. Vytvoření záznamu

Akce nezávislé na výběru. Vždy aktivní.

| Příklady z auditu | Typické moduly |
|---|---|
| Nový úkol, Nová událost, Nová událost ze šablony... | Agenda |
| Nový úraz | Kniha úrazů |
| Nové vyšetřování | Vyšetřování MU |
| Nový audit, Nová prověrka | Audity, Prověrky |
| Nová identifikace, Nový zdroj rizika, Nová revize | Řízení rizik |
| Nová koordinace | Koordinace BOZP |
| Nový proces, Nový | Právní požadavky |
| Přidat THP pracovníka, Nová osoba, Přidat roli, Přidat… | Nastavení |

### B. Úprava vybraného záznamu

Vyžaduje právě jeden výběr (`UX_STANDARD_001` § 2).

| Příklady | Poznámka |
|---|---|
| **Upravit** | Výchozí akce u většiny seznamů; dvojklik = Upravit |
| **Otevřít** | Jen pokud modul skutečně nepoužívá „Upravit“ jako otevření editoru (viz § 5 a STANDARD 001 § 6a) |

### C. Změna stavu

Vyžaduje právě jeden výběr + stav záznamu.

| Příklady z auditu | Modul / oblast |
|---|---|
| Aktivovat, Deaktivovat | Nastavení, Rizika, Koordinace |
| Archivovat, Obnovit | Revize posouzení rizik; Řídicí procesy (dnes dyn) |
| Deaktivovat ↔ Obnovit (dyn) | Právní předpisy / zjištěné změny |
| Splněno, Vrátit do aktivních, Zrušit / netrvá | Úkoly (legacy) |
| Provést revizi | Revize posouzení rizik |
| Označit jako vyhodnocené | Zjištěné změny |
| Smazat | MU, Audity, Prověrky (trvalé smazání záznamu) |
| Lifecycle (např. Vrátit k dopracování) | Koordinace |

**Smazat** patří do skupiny C jako destruktivní změna evidence záznamu
(není výstup ani správa).

### D. Odborné / navazující akce nad záznamem

Akce specifické pro doménu, které otevírají navazující proces (ne report).

| Příklady z auditu | Modul |
|---|---|
| Ohláška OO, Ohlašovací povinnosti, Vyšetřování MU | Kniha úrazů |
| Ověřit plnění, Vytvořit úkol, Platné znění | Právní |
| Provést kontrolu | Kontroly změn (bez výběru) |
| Sedmero | Vyšetřování MU (bez výběru – podpora) |

Poznámka: **Sedmero** a **Provést kontrolu** jsou v praxi spíš podpora (E),
pokud nevyžadují výběr. V návrhových příkladech (§ 11) je řadíme podle
skutečného významu v daném modulu.

### E. Výstupy a reporty nad záznamem

| Příklady z auditu | Modul |
|---|---|
| Výpis o pracovním úrazu, Závěrečná zpráva | Kniha úrazů |
| Protokol…, Podrobná zpráva… | Audity, Prověrky |
| Tisk protokolu | Koordinace |
| Export JSON | Právní předpisy |
| Roční zpráva | Audity, Prověrky (bez výběru řádku – roční agregát) |

Roční / programové výstupy **bez výběru řádku** patří stále do skupiny E,
ale na liště se umísťují vpravo spolu s ostatními výstupy (ne do A).

### F. Správa a podpůrné akce

Nezávislé na výběru řádku (nebo správa číselníků).

| Příklady z auditu | Modul |
|---|---|
| Šablony... | Agenda |
| Manažer auditů, Editor metodiky | Audity |
| Roční plán, Generovat prověrky, Editor znalostí | Prověrky |
| Pravidla bezpečné práce, Spravovat kategorie… | Rizika |
| Import procesů, Sloučit proces, Diagnostika registru | Právní |
| Import z internetu / TXT / JSON | Právní předpisy |
| Sedmero | MU |

### G. Hromadné akce

Podle auditu **na hlavních seznamech modulů prakticky neexistují**.

Skutečně nalezené blízké akce (mimo klasickou list lištu):

| Akce | Kde |
|---|---|
| Označit vybrané jako zkontrolované | Správa dat → Kvalita dat → analýza podobností |
| Označit vše / Zrušit označení | AI import dialogy |

Dokud modul nemá skutečnou multi-select akci, **skupina G se nepoužívá**.
Nevymýšlet hromadné akce jen kvůli vyplnění skupiny.

---

## 3. Jednotné pořadí skupin v liště

```text
[A Vytvoření] | [B Úprava] | [C Stav] | [D Odborné] | [E Výstupy] | [F Správa]   ……   [filtry]
```

Mapování na cíl ze zadání:

| Pořadí | Skupina | Obsah |
|---|---|---|
| 1 | A | vytvoření záznamu |
| 2 | B | úprava vybraného záznamu |
| 3 | C | změny stavu (včetně Smazat) |
| 4 | D | odborné / navazující akce nad záznamem |
| 5 | E | výstupy a reporty |
| 6 | F | správa, šablony a podpůrné akce |

Pravidla:

- Skupinu **vynechat**, pokud modul žádnou akci z ní nemá.
- Uvnitř skupiny: nejčastější akce vlevo.
- Více akcí vytvoření (Agenda: Nový úkol + Nová událost) zůstávají vedle sebe v A.
- Filtry a hledání vždy až po `stretch` vpravo.

---

## 4. Oddělovače

### Pravidlo

Vizuální oddělovač (`QFrame` / `QToolBar.addSeparator` / ekvivalent) se vkládá
**mezi dvě sousední neprázdné skupiny** A–F.

```text
[A] | [B] | [C] | [D] | [E] | [F]   ……   filtry
```

### Zákazy

- Nevkládat oddělovač mezi jednotlivá tlačítka uvnitř jedné skupiny.
- Nevkládat oddělovač před první ani za poslední skupinu „do vzduchu“.
- Nevkládat oddělovač, pokud na jedné straně skupina chybí
  (např. jen A a B → jeden oddělovač mezi A a B).
- Oddělovač mezi lištou akcí a filtry **není nutný**, pokud je mezi nimi `stretch`
  (dostatečné vizuální oddělení).

### Minimální příklad

```text
[Nový úraz] | [Upravit] | [Ohláška OO] [Ohlašovací povinnosti] [Vyšetřování MU] | [Výpis…] [Závěrečná zpráva]
```

---

## 5. Jednotné názvosloví

Terminologie respektuje význam. Respektuje také `UX_NAZVOSLOVI.md`.

### 5.1 Tabulka současný → doporučený

| Současný název (audit) | Doporučený jednotný název | Moduly | Výjimka / zdůvodnění |
|---|---|---|---|
| Nový úkol / Nová událost / Nový úraz / Nový audit / … | **Nový/Nová** + podstatné jméno entity | Agenda, Kniha, MU, Audity, Prověrky, Rizika, Koordinace, Právní | Rod podle entity (Nový úraz, Nová prověrka) |
| Přidat THP pracovníka / Přidat roli / Přidat | **Přidat** (+ upřesnění, pokud je potřeba) | Nastavení, nested listy | Číselník / položka do seznamu = Přidat (`UX_NAZVOSLOVI`) |
| Nová osoba / Nový provoz / … | **Nová/Nový** + entita | Nastavení | Hlavní evidence osoby/provozu = Nový, ne Přidat |
| Upravit | **Upravit** | většina seznamů | Výchozí |
| Otevřít (Koordinace, Kontroly změn, Změny) | **Upravit**, pokud otevírá stejný editor | Koordinace, Právní | Ponechat **Otevřít** jen u skutečně read-only / odlišného prohlížení (STANDARD 001 § 6a) |
| Otevřít + Upravit současně (Šablony) | pouze **Upravit** | Šablony | Audit: stejný handler |
| Detail / Zobrazit | — | audit nenalezl | Nezavádět |
| Aktivovat | **Aktivovat** | Nastavení, Rizika, Koordinace | |
| Deaktivovat | **Deaktivovat** | totéž | |
| Obnovit (po deaktivaci / archivu) | **Obnovit** | Přezkoumání; Právní (dnes dyn) | Nezaměňovat s **Aktivovat**, pokud workflow mluví o archivu |
| Archivovat | **Archivovat** | Přezkoumání, Řídicí procesy | |
| Deaktivovat / Obnovit (dyn jedno tlačítko) | dvě tlačítka **Deaktivovat** + **Obnovit** *(nebo Aktivovat, viz § 6)* | Právní | Do APPLY: dyn výjimka § 6.3 |
| Archivovat / Obnovit (dyn) | dvě tlačítka **Archivovat** + **Obnovit** | Řídicí procesy | Do APPLY: dyn výjimka § 6.3 |
| Aktivovat / Deaktivovat (legacy TableToolbar) | dvě tlačítka | nepoužito v live | Nezavádět kombinovaný label |
| Aktivní / neaktivní | **Aktivovat** / **Deaktivovat** | Prověrky knowledge | |
| Smazat | **Smazat** | MU, Audity, Prověrky | Trvalé smazání celého záznamu |
| Odebrat | **Odebrat** | Šablony, přílohy, nested | Odebrání položky ze seznamu / vazby |
| Zrušit / netrvá | **Zrušit / netrvá** | Úkoly | Stav úkolu ≠ Deaktivovat číselníku |
| Splněno | **Splněno** | Úkoly | |
| Vrátit do aktivních | **Vrátit do aktivních** | Úkoly | |
| Vrátit k dopracování | **Vrátit k dopracování** | Koordinace | `UX_NAZVOSLOVI` |
| Protokol z interního auditu... | ponechat **plný název výstupu** | Audity | Doménově specifický dokument |
| Zpráva z prověrky BOZP | ponechat plný název | Prověrky | |
| Podrobná zpráva… | ponechat plný název | Audity, Prověrky | |
| Výpis o pracovním úrazu | ponechat | Kniha úrazů | |
| Závěrečná zpráva | ponechat | Kniha úrazů | |
| Tisk protokolu | **Tisk protokolu** | Koordinace | |
| Export JSON | **Export JSON** | Právní | Typ formátu v názvu je užitečný |
| Roční zpráva | **Roční zpráva** | Audity, Prověrky | |
| Manažer auditů | **Manažer auditů** | Audity | |
| Editor metodiky / Editor znalostí | ponechat rozdílné názvy | Audity vs Prověrky | Různé produkty editoru |
| Šablony... | **Šablony...** | Agenda | Trojtečka = otevírá správu |
| Spravovat kategorie… | **Spravovat kategorie…** | Katalog rizik | |
| Označit jako vyhodnocené | **Označit jako vyhodnocené** | Změny legislativy | |
| Vytvořit úkol / Otevřít úkol | dyn jedno tlačítko OK | FindingTaskActions | Viz § 6.4 |

### 5.2 Pravidla Nový / Přidat / Vytvořit

| Situace | Použít |
|---|---|
| Nový hlavní záznam evidence | **Nový/Nová** + entita |
| Položka do číselníku / dynamického řádku | **Přidat** |
| Vytvořit úkol ze zjištění | **Vytvořit úkol** (existující dyn akce) |

Nepoužívat „Vytvořit“ jako obecnou náhradu za Nový/Přidat na list liště.

### 5.3 Pravidla Upravit / Otevřít

1. Výchozí: **Upravit**.
2. Nepoužívat současně Otevřít a Upravit pro stejný editor (STANDARD 001 § 6a).
3. **Otevřít** jen pokud:
   - jde o prohlížení bez editace, nebo
   - otevírá se jiný objekt než editor záznamu (soubor, umístění, zdrojový záznam).
4. Dvojklik = výchozí akce B (Upravit, výjimečně Otevřít).

### 5.4 Pravidla Smazat / Odebrat / Deaktivovat / Zrušit

| Význam | Text |
|---|---|
| Trvalé smazání celého záznamu | **Smazat** |
| Odebrání položky ze seznamu / vazby / přílohy | **Odebrat** |
| Soft-off aktivní evidence (číselníky, identifikace…) | **Deaktivovat** (+ **Aktivovat**) |
| Stav „úkol netrvá“ | **Zrušit / netrvá** |
| Zrušení plánované návštěvy | **Zrušit návštěvu** (Manažer auditů) |

---

## 6. Stavová tlačítka

### 6.1 Výchozí pravidlo – dvě samostatná tlačítka

Pro páry aktivní ↔ neaktivní:

```text
[Aktivovat] [Deaktivovat]
```

- **Aktivovat** enabled jen při jednom výběru neaktivního záznamu.
- **Deaktivovat** enabled jen při jednom výběru aktivního záznamu.
- Bez výběru / více výběrů: obě OFF (`UX_STANDARD_001`).

Toto je současný vzor v **Nastavení**, **Řízení rizik** a **Koordinaci**.  
Je to **preferovaný** vzor pro nové úpravy.

### 6.2 Archivace – dvě samostatná tlačítka

Pro páry v evidenci / mimo evidenci (archiv):

```text
[Archivovat] [Obnovit]
```

Vzor: **Revize posouzení rizik**.

- **Archivovat** jen u nearchivovaného záznamu.
- **Obnovit** jen u archivovaného.
- Text **Obnovit** zde znamená návrat z archivu, ne „Aktivovat“ číselníku.

### 6.3 Dynamicky přejmenované tlačítko – omezené použití

**Jedno tlačítko s `setText` (Deaktivovat↔Obnovit / Archivovat↔Obnovit) se nově nezavádí.**

Dočasně povolené výjimky (dokud modul neprojde APPLY STANDARD 003):

| Místo | Současný vzor | Cíl při APPLY |
|---|---|---|
| Právní – Řídicí procesy | Archivovat↔Obnovit | dvě tlačítka Archivovat + Obnovit |
| Právní – Předpisy / Zjištěné změny | Deaktivovat↔Obnovit | dvě tlačítka Deaktivovat + **Aktivovat** *(nebo Obnovit, pokud workflow trvá na Obnovit – rozhodnout v APPLY Právní)* |
| EntityLinksWidget, legal sections/versions/sanctions | dyn | stejné jako nadřazený vzor číselníku |
| Legacy `TableToolbar` | Aktivovat / Deaktivovat | nepoužívat |

Doporučení pro Právní při APPLY: sjednotit na **Aktivovat / Deaktivovat**
u předpisů a zjištěných změn (stejný význam jako Nastavení), a **Archivovat / Obnovit**
u řídicích procesů (archivace procesu).
**Kontroly změn** toto ovládání nemají: `LegalCheckRun.active` je interní
historický soft-off, v běžném UI se nezobrazuje ani neovládá
(RPP-CHECK-ACTIVE-2).

### 6.4 Povolené dynamické tlačítko (trvalé výjimky)

Dyn label je **přípustný**, pokud nejde o pouhý toggle aktivní/neaktivní, ale o
**různou akci ve stejném slotu**:

| Komponenta | Label | Důvod |
|---|---|---|
| `FindingTaskActions` | Vytvořit úkol ↔ Otevřít úkol | Mutually exclusive: buď vytvořit, nebo otevřít existující |
| Koordinace lifecycle | např. Vrátit k dopracování | Label = konkrétní povolený přechod stavu |
| Manažer auditů | Rozdělit procesy ↔ Doplnit nové procesy | Stejný slot, jiný režim podle stavu programu |

Tato dyn tlačítka **nejsou** náhradou za Aktivovat/Deaktivovat.

### 6.5 Další stavové přechody

| Akce | Pravidlo |
|---|---|
| Provést revizi | Samostatné tlačítko ve skupině C/D; enabled jen pokud dává smysl stav |
| Označit jako… | Samostatné; enabled podle stavu (např. nevyhodnoceno) |
| Splněno / Vrátit do aktivních / Zrušit / netrvá | Samostatná tlačítka (Úkoly); ne slučovat |
| Smazat | Samostatné ve skupině C; s potvrzením; ne jako Deaktivovat |
| Uzavřít | V editoru (lifecycle), ne v list liště – viz `UX_NAZVOSLOVI` |

### 6.6 Zakázané

- Kombinovaný label **„Aktivovat / Deaktivovat“** na jednom tlačítku.
- Kombinovaný label **„Aktivní / neaktivní“** na list/editor seznamech.
- Zobrazovat současně Aktivovat i Deaktivovat jako enabled u stejného záznamu.

---

## 7. Ikony

### 7.1 Stav podle auditu

| Oblast | Ikony na list liště |
|---|---|
| Agenda, Kniha, MU, Audity, Prověrky, Rizika, Koordinace, Právní, Nastavení (hlavní seznamy) | **bez** `QIcon` – pouze text |
| Pracovní plocha (rychlé akce) | emoji v textu: `💾 Záloha`, `♻ Obnova`, `+ Úraz` |
| Nested / editory | občas emoji v textu (`➕ Založit zjištění`, `✏ Upravit znalosti`, `🧠 Vysvětlení…`) |
| Titulky sekcí | např. `📷 Referenční fotografie` |

### 7.2 Pravidla

1. Stejná akce = stejná ikona (`UI_KOMPONENTY.md` § 12).
2. Ikona **nesmí nahrazovat** srozumitelný text na list liště.
3. **Nevynucovat** ikony do modulů, které je na list liště nepoužívají.
4. V této fázi **nevytvářet ani neměnit** ikony / emoji.
5. Pokud se ikony později doplní, nejdřív jednotný katalog a teprve APPLY po modulech.

---

## 8. Šířka a délka lišty

1. **Nejčastější akce vlevo** (A → B → C).
2. **Vzácné správcovské akce vpravo** ve skupině F (Import, Diagnostika, Editor…).
3. Při nedostatku místa přesouvat **nejprve F**, pak méně časté E, nikoli A/B.
4. Neslučovat dvě přímé často používané akce do menu jen kvůli místu.
5. Rozbalovací menu jen pokud obsahuje **≥ 2** související akce.
6. Dlouhé názvy výstupů (Protokol z interního auditu...) je dovoleno ponechat –
   srozumitelnost > zkracování.
7. Filtry vždy vpravo za stretch; nesmí vytlačovat A/B z viditelné oblasti
   bez možnosti horizontálního řešení layoutu modulu.

---

## 9. Kontextová menu

### 9.1 Vztah k liště

| Pravidlo | Detail |
|---|---|
| Hlavní akce nad výběrem | Ctx **má** obsahovat B + relevantní C + často D/E vázané na výběr |
| Podpůrné F | Ctx **nemusí** opakovat (Šablony, Editor znalostí, Import…) |
| Názvy | Stejné jako na liště |
| Aktivace | Stejná pravidla jako lišta (`UX_STANDARD_001`) |
| Dvojklik | Stále výchozí B (ne nahrazuje ctx) |

### 9.2 Absence kontextového menu

Podle auditu **není automaticky chyba**:

| Místo | Stav |
|---|---|
| Koordinace (hlavní + editor taby) | bez ctx |
| Kontroly (matice) | bez ctx |
| Šablony událostí | bez ctx |
| Úkoly (legacy) | bez ctx |
| Správa dat (většina) | bez ctx (strom číselníků má ctx) |

Při APPLY STANDARD 003:

- u klasických seznamů (jako Agenda/Kniha) **doporučit** ctx pro B/C/D/E,
- u matic a netabulkových obrazovek ctx nevyžadovat,
- u Koordinace: doplnění ctx je volitelné vylepšení, ne blokující povinnost
  (lišta + klávesnice už existují).

---

## 10. Výjimky z rozsahu lišty

| Obrazovka | Důvod |
|---|---|
| Kontroly | Matice bez list toolbaru – STANDARD 003 se neaplikuje na neexistující lištu |
| Pracovní plocha | Quick actions ≠ seznamová lišta |
| O programu | Jen OK |
| Zaměstnavatel (Nastavení) | Formulář, ne seznam |
| Spodní lišta editorů | Řídí `UI_KOMPONENTY.md` |
| Nested seznamy v editoru | Sledují stejné **názvy a stavová pravidla**, ale layout může být kompaktnější; oddělovače skupin A–F nejsou povinné |

---

## 11. Návrhové příklady lišt (podle auditu)

Použity **jen akce nalezené auditem**. Oddělovače = `|`.  
Pořadí = cílový stav po APPLY STANDARD 003 (může se lišit od dnešního kódu).

### Agenda

```text
[Nový úkol] [Nová událost] [Nová událost ze šablony...] | [Upravit] | [Šablony...]
```

- A: tři vytvoření  
- B: Upravit  
- F: Šablony...  
- Ctx: Upravit  
- Dvojklik: Upravit

### Kniha úrazů

```text
[Nový úraz] | [Upravit] | [Ohláška OO] [Ohlašovací povinnosti] [Vyšetřování MU] | [Výpis o pracovním úrazu] [Závěrečná zpráva]
```

- A | B | D | E  
- Ctx: Upravit + D + E  
- Dvojklik: Upravit

### Vyšetřování MU

```text
[Nové vyšetřování] | [Upravit] | [Smazat] | [Sedmero]
```

- A | B | C | F (Sedmero = podpora bez výběru)  
- Ctx: Upravit, Smazat  
- Dvojklik: Upravit

### Audity systémů řízení

```text
[Nový audit] | [Upravit] | [Smazat] | [Protokol z interního auditu...] [Podrobná zpráva z interního auditu...] [Roční zpráva] | [Manažer auditů] [Editor metodiky]
```

- A | B | C | E | F  
- Protokoly v E enabled jen při stavu Dokončeno (STANDARD 001)  
- Ctx: Upravit, Smazat, protokoly (pokud enabled)  
- Dvojklik: Upravit

### Prověrky BOZP

```text
[Nová prověrka] | [Upravit] | [Smazat] | [Zpráva z prověrky BOZP] [Podrobná zpráva z prověrky BOZP] [Roční zpráva] | [Roční plán] [Generovat prověrky] [Editor znalostí]
```

- A | B | C | E | F  
- Ctx: Upravit, Smazat, zprávy (pokud enabled)  
- Dvojklik: Upravit

### Řízení rizik – Identifikace

```text
[Nová identifikace] | [Upravit] | [Aktivovat] [Deaktivovat] | [Pravidla bezpečné práce]
```

### Řízení rizik – Katalog zdrojů rizik

```text
[Nový zdroj rizika] | [Upravit] | [Aktivovat] [Deaktivovat] | [Spravovat kategorie…]
```

### Řízení rizik – Revize posouzení rizik

```text
[Nová revize] | [Upravit] | [Provést revizi] [Archivovat] [Obnovit]
```

- Stavová skupina C obsahuje Provést + Archivovat + Obnovit (vše nad výběrem)  
- Dvě tlačítka Archivovat / Obnovit (ne dyn)

### Právní požadavky – Řídicí procesy *(cílový stav)*

```text
[Nový proces] | [Upravit] | [Archivovat] [Obnovit] | [Ověřit plnění] [Vytvořit úkol] | [Import procesů] [Sloučit proces] [Diagnostika registru]
```

Současný kód: jedno dyn Archivovat/Obnovit – výjimka § 6.3 do APPLY.

### Právní požadavky – Právní předpisy *(cílový stav)*

```text
[Nový] | [Upravit] | [Aktivovat] [Deaktivovat] | [Platné znění] | [Export JSON] | [Import z internetu] [Import TXT] [Import JSON]
```

### Právní požadavky – Kontroly změn *(cílový stav)*

```text
[Provést kontrolu] | [Otevřít*]
```

\*Do rozhodnutí § 5.3: pokud editor běhu = editace, přejmenovat na **Upravit**.

Historické kontroly se zobrazují jako běžná historie. Sloupec **Aktivní**
ani tlačítka **Aktivovat** / **Deaktivovat** / **Obnovit** se v tomto
seznamu nevytvářejí (`LegalCheckRun.active` zůstává jen interně).

### Právní požadavky – Zjištěné změny *(cílový stav)*

```text
[Otevřít*] | [Aktivovat] [Deaktivovat] | [Označit jako vyhodnocené]
```

### Nastavení – typický číselník (THP / Osoby / Role / Ohrožené skupiny)

```text
[Přidat… / Nová…] | [Upravit] | [Aktivovat] [Deaktivovat]
```

- A | B | C  
- Ctx: Upravit, Aktivovat, Deaktivovat  
- Dvojklik: Upravit  
- Již odpovídá preferovanému vzoru po APPLY-010

### Nastavení – Provozy a pracoviště

```text
[Nový provoz] [Nové pracoviště] [Nová část pracoviště] | [Upravit] | [Aktivovat] [Deaktivovat]
```

---

## 12. Zavádění

1. Schválit tento dokument.
2. Zavádět **modul po modulu** podle levého menu.
3. Jeden modul = jeden commit.
4. Při APPLY:
   - upravit pořadí a oddělovače,
   - sjednotit názvy dle § 5,
   - převést dyn toggle na dvě tlačítka dle § 6 (kde platí),
   - sjednotit ctx s lištou dle § 9,
   - doplnit/upravit testy layoutu a aktivace,
   - **neměnit** význam business logiky bez samostatného důvodu.
5. `UX_BUTTON_AUDIT_001.md` se při APPLY **nemění** (historický podklad);
   případně vznikne nový audit později.

---

## 13. Související dokumenty

| Dokument | Role |
|---|---|
| `UX_STANDARD_001.md` | Kdy je tlačítko enabled |
| `UX_STANDARD_003.md` | Tento dokument – pořadí, skupiny, názvy, vzhled lišty |
| `UX_BUTTON_AUDIT_001.md` | Inventura skutečného stavu |
| `UX_NAZVOSLOVI.md` | Obecné texty UI |
| `UI_KOMPONENTY.md` | Komponenty, spodní lišta, ikony obecně |

---

## Verze

**UX STANDARD č. 003**  
Jednotná horní lišta seznamových modulů  

Podklad: UX-BUTTON-AUDIT-001  
Stav: návrh ke schválení (bez změny aplikačního kódu)
